"""Repeatable local-only MOCK registration journey; never resets or deletes data.

Run inside the isolated Compose web container after startup. Credentials come only
from its private environment. Use --expect-pending while the gateway is stopped,
then rerun the same scenario after restart to prove recovery without a second debit.
"""

import argparse
import hashlib
import time
from datetime import date, timedelta

import httpx

from app.config import settings
from app.leave_calendar import charged_days
from app.provision_demo import DEMO_ACCOUNTS


def run_smoke(client, scenario, *, expect_pending=False, wait_seconds=90):
    if settings.ENVIRONMENT == "production" or not settings.DEMO_MODE:
        raise RuntimeError("Smoke requires non-production DEMO_MODE")
    if not settings.INTEGRATION_GATEWAY_URL or settings.AI_PROVIDER != "grounded_knowledge":
        raise RuntimeError("Smoke requires the internal MOCK gateway and offline AI")
    tokens = []

    def call(method, path, *, token=None, expected=200, **kwargs):
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = "Bearer " + token
        response = client.request(method, "/api/v1" + path, headers=headers, **kwargs)
        assert response.status_code == expected, f"{method} {path}: HTTP {response.status_code}"
        return response.json()

    try:
        for role in ("employee", "manager", "hr_admin"):
            result = call(
                "POST",
                "/auth/login",
                json={"email": DEMO_ACCOUNTS[role], "password": settings.DEMO_PASSWORD},
            )
            assert result["user"]["role"] == role
            tokens.append(result["access_token"])
        employee, manager, hr = tokens
        config = call("GET", "/config")
        assert config["demo_mode"]
        profile = call("GET", "/me/profile", token=employee)
        assert profile["employee_code"] == "DEMO-EMP-001"
        assert not profile["is_official_hr_data"]
        existing = []
        offset = 0
        while True:
            page = call("GET", f"/requests?limit=100&offset={offset}", token=employee)
            existing.extend(page)
            if len(page) < 100:
                break
            offset += 100
        marker = "Synthetic MOCK integration scenario " + scenario
        previous = next((r for r in existing if r["reason"] == marker), None)
        start = date.today() + timedelta(days=30)
        if previous:
            start = date.fromisoformat(previous["start_date"])
        else:
            for _ in range(300):
                if charged_days(start, start) and not any(
                    r["type"] == "Vacation"
                    and r["status"] in {"Pending", "Approved"}
                    and r["start_date"] <= start.isoformat() <= (r["end_date"] or r["start_date"])
                    for r in existing
                ):
                    break
                start += timedelta(days=1)
            else:
                raise RuntimeError("No free synthetic period; choose a new isolated fixture")
        payload = {
            "type": "Vacation",
            "start_date": start.isoformat(),
            "end_date": start.isoformat(),
            "reason": marker,
        }
        key = "integration-smoke-" + hashlib.sha256(scenario.encode()).hexdigest()[:32]
        submitted = call(
            "POST",
            "/requests",
            token=employee,
            expected=201,
            headers={"Idempotency-Key": key},
            json=payload,
        )
        repeat = call(
            "POST",
            "/requests",
            token=employee,
            expected=201,
            headers={"Idempotency-Key": key},
            json=payload,
        )
        assert submitted["id"] == repeat["id"]
        path = f"/requests/{submitted['id']}"
        was_approved = submitted["status"] == "Approved"
        if not was_approved:
            call("POST", path + "/approve", token=manager)
        current = call("GET", path, token=employee)
        assert current["status"] == "Approved"
        after = call("GET", "/me/profile", token=employee)
        assert after["leave_balance_days"] == profile["leave_balance_days"] - (
            0 if was_approved else current["vacation_days"]
        )
        if expect_pending:
            assert current["sync_status"] in {"PENDING", "SENT"}
            assert not current["external_ref"]
        else:
            deadline = time.monotonic() + wait_seconds
            while current["sync_status"] in {"PENDING", "SENT"} and time.monotonic() < deadline:
                time.sleep(0.5)
                current = call("GET", path, token=employee)
            assert current["sync_status"] == "REGISTERED", "Registration did not complete"
            assert current["integration_mode"] == "MOCK"
            assert current["external_ref"].startswith("MOCK-DOC-")
            notifications = []
            offset = 0
            while True:
                page = call("GET", f"/notifications?limit=100&offset={offset}", token=employee)
                notifications.extend(page)
                if len(page) < 100:
                    break
                offset += 100
            assert (
                sum(
                    n["reference_id"] == current["request_code"]
                    and n["title"] == "MOCK document registered"
                    for n in notifications
                )
                == 1
            )
            cards = call("GET", "/admin/integrations", token=hr)
            assert all(c["mode"] == "MOCK" for c in cards)
        call("GET", "/manager/requests", token=employee, expected=403)
        call("GET", "/admin/integrations/queue", token=employee, expected=403)
        # Only safe identifiers/statuses are printed. No payloads, tokens or credentials.
        summary = {
            "scenario": scenario,
            "request_code": current["request_code"],
            "business_status": current["status"],
            "integration_status": current["sync_status"],
            "external_ref": current["external_ref"],
            "reused_request": was_approved,
        }
        print(summary)
        return summary
    finally:
        for token in tokens:
            client.post("/api/v1/auth/logout", headers={"Authorization": "Bearer " + token})


def main():
    from app.database import SessionLocal, engine
    from app.migrate import require_current_schema
    from app.provision_demo import provision_accounts

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="repeatable-v1")
    parser.add_argument("--expect-pending", action="store_true")
    args = parser.parse_args()
    if not 1 <= len(args.scenario) <= 80 or not all(
        c.isascii() and (c.isalnum() or c in "_-") for c in args.scenario
    ):
        parser.error("Scenario must be 1–80 ASCII letters, digits, underscores or hyphens")
    if settings.ENVIRONMENT == "production" or not settings.DEMO_MODE:
        parser.error("Smoke is disabled outside a non-production demo")
    require_current_schema(engine)
    with SessionLocal() as db:
        provision_accounts(db)
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10, trust_env=False) as client:
        run_smoke(client, args.scenario, expect_pending=args.expect_pending)


if __name__ == "__main__":
    main()
