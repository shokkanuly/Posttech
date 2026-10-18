"""Section 10 acceptance: approval -> signed durable MOCK job -> signed callback."""

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import httpx
import pytest

from app.config import Settings, settings
from app.gateway.models import GatewayJob
from app.integrations import outbox, profile_sync, signing
from app.integrations.contracts import CALLBACK_PATH
from app.models.integration import IntegrationOutbox, IntegrationReview
from app.models.notification import Notification
from app.models.profile import EmployeeProfile
from app.models.request import Request
from tests.test_gateway_service import APP_KEY, CALLBACK_KEY, gateway_client

__all__ = ["gateway_client"]


@pytest.fixture
def connected(gateway_client, client, monkeypatch):
    monkeypatch.setattr(settings, "INTEGRATION_GATEWAY_URL", "http://gateway.test")
    monkeypatch.setattr(settings, "INTEGRATION_OUTBOUND_KEY_ID", "app-1")
    monkeypatch.setattr(settings, "INTEGRATION_OUTBOUND_KEY", APP_KEY)
    monkeypatch.setattr(settings, "INTEGRATION_INBOUND_KEYS", {"gw-1": CALLBACK_KEY})

    def gateway_transport(method, url, **kwargs):
        kwargs.pop("verify", None)
        kwargs.pop("timeout", None)
        parsed = urlsplit(url)
        return gateway_client.request(
            method, parsed.path + ("?" + parsed.query if parsed.query else ""), **kwargs
        )

    def callback_transport(url, **kwargs):
        kwargs.pop("verify", None)
        kwargs.pop("timeout", None)
        return client.post(urlsplit(url).path, **kwargs)

    monkeypatch.setattr(outbox.httpx, "request", gateway_transport)
    monkeypatch.setattr(outbox.httpx, "post", callback_transport)
    return gateway_client.app.state.runtime


def approve_vacation(client, employee_headers, manager_headers):
    created = client.post(
        "/api/v1/requests",
        headers=employee_headers,
        json={
            "type": "Vacation",
            "start_date": "2026-12-01",
            "end_date": "2026-12-02",
            "reason": "NEVER-SEND-ME",
        },
    )
    assert created.status_code == 201
    rid = created.json()["id"]
    result = client.post(f"/api/v1/requests/{rid}/approve", headers=manager_headers)
    assert result.status_code == 200
    return rid


def test_short_integration_keys_are_refused():
    with pytest.raises(ValueError, match="at least 32"):
        Settings(INTEGRATION_INBOUND_KEYS={"gw-1": "short"})


def test_without_gateway_approval_queues_nothing(
    client, db_session, employee_headers, manager_headers
):
    rid = approve_vacation(client, employee_headers, manager_headers)
    assert db_session.query(IntegrationOutbox).count() == 0
    assert db_session.get(Request, rid).integration_status is None


def test_signed_full_journey_notifies_exactly_once(
    client, db_session, employee_headers, manager_headers, connected
):
    rid = approve_vacation(client, employee_headers, manager_headers)
    task = db_session.query(IntegrationOutbox).one()
    assert task.payload["kind"] == "VACATION_REQUEST"
    assert "NEVER-SEND-ME" not in json.dumps(task.payload)
    assert not {"full_name", "reason", "email", "salary"} & task.payload.keys()
    assert outbox.dispatch_one(db_session)
    db_session.expire_all()
    assert db_session.get(Request, rid).integration_status == "SENT"
    assert connected.process_one() and connected.callback_one()
    db_session.expire_all()
    req = db_session.get(Request, rid)
    assert req.status.value == "Approved" and req.integration_status == "REGISTERED"
    assert req.external_sync_id.startswith("MOCK-DOC-")
    assert db_session.query(Notification).filter_by(title="MOCK document registered").count() == 1
    # Fresh callback signature/result may be delivered again: state and notice stay idempotent.
    with connected.sessions() as db:
        job = db.query(GatewayJob).one()
        job.callback_status = "PENDING"
        db.commit()
    assert connected.callback_one()
    db_session.expire_all()
    assert db_session.query(Notification).filter_by(title="MOCK document registered").count() == 1
    detail = client.get(f"/api/v1/requests/{rid}", headers=employee_headers).json()
    assert detail["sync_status"] == "REGISTERED" and detail["integration_mode"] == "MOCK"
    assert detail["external_ref"] == req.external_sync_id


def test_approval_survives_gateway_down_retries_then_dead(
    client, db_session, employee_headers, manager_headers, connected, monkeypatch
):
    rid = approve_vacation(client, employee_headers, manager_headers)

    def down(*args, **kwargs):
        raise httpx.ConnectError("network unavailable")

    monkeypatch.setattr(outbox.httpx, "request", down)
    for attempt in range(1, 9):
        assert outbox.dispatch_one(db_session)
        task = db_session.query(IntegrationOutbox).one()
        assert task.attempts == attempt
        if attempt < 8:
            assert task.status == "PENDING"
            assert not outbox.dispatch_one(db_session)
            task.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db_session.commit()
    assert task.status == "DEAD" and task.last_error == "NETWORK"
    assert db_session.get(Request, rid).status.value == "Approved"
    assert (
        db_session.query(Notification).filter_by(title="Integration delivery failed").count() == 1
    )
    assert client.get("/api/v1/me/profile", headers=employee_headers).status_code == 200


def test_malformed_ack_is_not_success(
    client, db_session, employee_headers, manager_headers, connected
):
    rid = approve_vacation(client, employee_headers, manager_headers)
    assert outbox.dispatch_one(db_session, send=lambda *_: (202, {}))
    req = db_session.get(Request, rid)
    assert req.integration_status == "PENDING" and req.external_sync_id is None
    assert db_session.query(IntegrationOutbox).one().last_error == "INVALID_ACK"


def test_validation_failure_not_retried_and_hr_queue_shows_it(
    client, db_session, employee_headers, manager_headers, hr_admin_headers, connected
):
    rid = approve_vacation(client, employee_headers, manager_headers)
    connected.config.MOCK_DOCUMENTOLOG_FAILURE = "validation"
    assert outbox.dispatch_one(db_session)
    assert connected.process_one() and connected.callback_one()
    db_session.expire_all()
    assert db_session.get(Request, rid).integration_status == "FAILED"
    assert not outbox.dispatch_one(db_session)
    queue = client.get("/api/v1/admin/integrations/queue", headers=hr_admin_headers).json()
    assert len(queue) == 1 and queue[0]["status"] == "FAILED" and queue[0]["mode"] == "MOCK"


def test_reconciliation_recovers_lost_callback(
    client, db_session, employee_headers, manager_headers, connected
):
    rid = approve_vacation(client, employee_headers, manager_headers)
    outbox.dispatch_one(db_session)
    connected.process_one()
    task = db_session.query(IntegrationOutbox).one()
    task.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    assert outbox.dispatch_one(db_session)
    assert db_session.get(Request, rid).integration_status == "REGISTERED"
    assert connected.callback_one()
    assert db_session.query(Notification).filter_by(title="MOCK document registered").count() == 1


def test_bearer_cannot_callback_and_tampered_or_replay_callback_rejected(
    client, db_session, employee_headers, manager_headers, connected, monkeypatch
):
    approve_vacation(client, employee_headers, manager_headers)
    assert client.post(CALLBACK_PATH, headers=employee_headers, json={}).status_code == 401
    outbox.dispatch_one(db_session)
    connected.process_one()
    captured = []

    def capture(url, **kwargs):
        captured.append(kwargs)
        return client.post(CALLBACK_PATH, content=kwargs["content"], headers=kwargs["headers"])

    monkeypatch.setattr(outbox.httpx, "post", capture)
    assert connected.callback_one()
    wire = captured[0]
    assert (
        client.post(CALLBACK_PATH, content=wire["content"], headers=wire["headers"]).status_code
        == 401
    )
    assert (
        client.post(
            CALLBACK_PATH, content=wire["content"] + b" ", headers=wire["headers"]
        ).status_code
        == 401
    )
    stale = signing.sign(
        "gw-1",
        CALLBACK_KEY,
        "POST",
        CALLBACK_PATH,
        wire["content"],
        now=datetime.now().timestamp() - 301,
    )
    assert client.post(CALLBACK_PATH, content=wire["content"], headers=stale).status_code == 401


def test_profile_sync_code_matching_and_provisional_balance(
    client, db_session, employee_headers, manager_headers, connected
):
    rid = approve_vacation(client, employee_headers, manager_headers)
    assert profile_sync.sync_profiles(db_session, force=True)["status"] == "ok"
    profile = client.get("/api/v1/me/profile", headers=employee_headers).json()
    assert profile["source_mode"] == "MOCK" and not profile["is_official_hr_data"]
    assert profile["leave_balance_days"] == 16.5  # snapshot18.5 minus unconfirmed local2, once
    assert profile["read_only"] and profile["as_of"]
    req = db_session.get(Request, rid)
    snapshot = next(r for r in connected.one_c.rows if r.employee_code == "JP-10428")
    confirmed = snapshot.model_copy(
        update={"leave_balance_days": 16.5, "confirmed_request_codes": [req.request_code]}
    )
    assert profile_sync.apply_snapshot(db_session, confirmed, "MOCK")
    db_session.commit()
    assert (
        client.get("/api/v1/me/profile", headers=employee_headers).json()["leave_balance_days"]
        == 16.5
    )
    db_session.refresh(req)
    assert req.leave_balance_confirmed


def test_unmatched_employee_and_manager_go_to_review(client, db_session, connected):
    before = db_session.query(EmployeeProfile).count()
    row = connected.one_c.rows[1]
    unmatched = row.model_copy(update={"employee_code": "UNKNOWN-TEST"})
    assert not profile_sync.apply_snapshot(db_session, unmatched, "MOCK")
    assert not profile_sync.apply_snapshot(
        db_session, row.model_copy(update={"manager_employee_code": "UNKNOWN-MANAGER"}), "MOCK"
    )
    db_session.commit()
    assert db_session.query(EmployeeProfile).count() == before
    assert db_session.get(IntegrationReview, "UNKNOWN-TEST").reason == "UNKNOWN_EMPLOYEE"
    assert db_session.get(IntegrationReview, "JP-10428").reason == "UNKNOWN_MANAGER"


def test_refresh_is_hr_only_rate_limited_and_stale_snapshot_survives_outage(
    client, db_session, employee_headers, manager_headers, hr_admin_headers, connected
):
    assert (
        client.post("/api/v1/admin/integrations/refresh", headers=employee_headers).status_code
        == 403
    )
    assert (
        client.post("/api/v1/admin/integrations/refresh", headers=manager_headers).status_code
        == 403
    )
    assert (
        client.post("/api/v1/admin/integrations/refresh", headers=hr_admin_headers).status_code
        == 200
    )
    assert (
        client.post("/api/v1/admin/integrations/refresh", headers=hr_admin_headers).status_code
        == 429
    )
    profile = client.get("/api/v1/me/profile", headers=employee_headers).json()
    connected.config.MOCK_ONE_C_UNAVAILABLE = True
    from app.models.integration import IntegrationSyncState

    state = db_session.get(IntegrationSyncState, "one_c")
    state.last_attempt_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()
    result = client.post("/api/v1/admin/integrations/refresh", headers=hr_admin_headers)
    assert result.json()["status"] == "unavailable"
    old = client.get("/api/v1/me/profile", headers=employee_headers)
    assert (
        old.status_code == 200 and old.json()["leave_balance_days"] == profile["leave_balance_days"]
    )
    assert old.json()["is_stale"]


def test_admin_card_uses_actual_counts_mode_and_last_success(
    client, db_session, employee_headers, manager_headers, hr_admin_headers, connected
):
    approve_vacation(client, employee_headers, manager_headers)
    before = client.get("/api/v1/admin/integrations", headers=hr_admin_headers).json()[1]
    assert before["pending_count"] == 1 and before["last_success"] is None
    outbox.dispatch_one(db_session)
    connected.process_one()
    connected.callback_one()
    card = client.get("/api/v1/admin/integrations", headers=hr_admin_headers).json()[1]
    assert (
        card["mode"] == "MOCK" and card["pending_count"] == 0 and card["last_success"] is not None
    )
    assert card["synced_records_count"] == 1
    assert (
        client.get("/api/v1/admin/integrations/queue", headers=employee_headers).status_code == 403
    )


def test_snapshot_failure_does_not_confirm_debits_or_overwrite_balance(
    client, db_session, employee_headers, manager_headers, connected
):
    rid = approve_vacation(client, employee_headers, manager_headers)
    req = db_session.get(Request, rid)
    profile = db_session.query(EmployeeProfile).filter_by(employee_code="JP-10428").one()
    original_balance = profile.leave_balance_days
    snapshot = connected.one_c.rows[1].model_copy(update={"leave_balance_days": 0.0})
    assert not profile_sync.apply_snapshot(db_session, snapshot, "MOCK")
    db_session.commit()
    db_session.refresh(req)
    db_session.refresh(profile)
    assert not req.leave_balance_confirmed and profile.leave_balance_days == original_balance
    assert db_session.get(IntegrationReview, "JP-10428").reason == "BALANCE_CONFLICT"
