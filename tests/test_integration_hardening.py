"""Canonical compatibility, durable admission limits and private demo configuration."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from dotenv import dotenv_values
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import Headers

from app.gateway import runtime as runtime_module
from app.gateway.main import create_app
from app.gateway.models import GatewayJob, GatewayNonce, GatewayRateLimit
from app.gateway.runtime import GatewayRuntime
from app.integrations import signing
from tests.test_gateway_service import APP_KEY, config_for, document, signed
from tests.test_integration_gateway import approve_vacation, connected, gateway_client

__all__ = ["connected", "gateway_client"]


@pytest.mark.parametrize(
    "method,path,body,expected",
    [
        (
            "post",
            "/v1/documents?x=a%2Fb&x=a+b",
            '{"employee":"Синтетика"}\n'.encode(),
            "5mgw3OOdTnSiZbP+3Ffp4aWcjG5LK0iyjjP4eQ4uM1c=",
        ),
        (
            "GET",
            "/v1/employees?updated_since=2026-10-17T08%3A00%3A00%2B00%3A00",
            b"",
            "ZZCYswsYp0ojMBUKS8LqoGPkZ+hgRmNSEntGaAocQP0=",
        ),
    ],
)
def test_signing_openssl_golden_vectors(method, path, body, expected):
    # Digests independently generated with openssl dgst -sha256 -hmac ... -binary.
    headers = signing.sign(
        "vector",
        "canonical-vector-key",
        method,
        path,
        body,
        now=1792224000,
        nonce="vector_nonce_00000001",
    )
    assert headers["X-Signature"] == expected
    for delta in (-300, 300):
        assert (
            signing.verify(
                Headers(headers),
                {"vector": "canonical-vector-key"},
                method,
                path,
                body,
                now=1792224000 + delta,
            )
            == "vector_nonce_00000001"
        )
    for delta in (-301, 301):
        with pytest.raises(signing.SignatureError):
            signing.verify(
                Headers(headers),
                {"vector": "canonical-vector-key"},
                method,
                path,
                body,
                now=1792224000 + delta,
            )
    for changed_path, changed_body in [(path + "&extra=1", body), (path, body + b" ")]:
        with pytest.raises(signing.SignatureError):
            signing.verify(
                Headers(headers),
                {"vector": "canonical-vector-key"},
                method,
                changed_path,
                changed_body,
                now=1792224000,
            )


def test_signed_limits_survive_restart_and_reset_per_key_per_minute(tmp_path, monkeypatch):
    clock = datetime(2026, 10, 18, 9, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(runtime_module, "utcnow", lambda: clock)
    config = config_for(tmp_path / "limited.db")
    config.REQUESTS_PER_MINUTE = 1
    replay = signing.sign("app-1", APP_KEY, "GET", "/health", b"")
    with TestClient(create_app(config)) as first:
        assert first.get("/health", headers=replay).status_code == 200
        denied = signed(first, "POST", "/v1/documents", document())
        assert denied.status_code == 429 and denied.headers["Retry-After"] == "60"
        assert denied.headers["Cache-Control"] == "no-store"
        with first.app.state.runtime.sessions() as db:
            assert db.query(GatewayJob).count() == 0
            assert db.query(GatewayNonce).count() == 1
    config.JANAMEN_KEYS["rotated"] = APP_KEY
    with TestClient(create_app(config)) as restarted:
        assert signed(restarted, "GET", "/health").status_code == 429
        other = signing.sign("rotated", APP_KEY, "GET", "/health", b"")
        assert restarted.get("/health", headers=other).status_code == 200
        clock += timedelta(minutes=1)
        # Replay still fails, and its rolled-back quota increment does not consume the window.
        assert restarted.get("/health", headers=replay).status_code == 401
        assert signed(restarted, "POST", "/v1/documents", document()).status_code == 202


def test_concurrent_quota_is_atomic_on_supported_databases(db_engine, tmp_path, monkeypatch):
    config = config_for(tmp_path / "unused.db")
    config.REQUESTS_PER_MINUTE = 3
    runtime = GatewayRuntime(config)
    runtime.engine.dispose()
    runtime.engine = db_engine
    runtime.sessions = sessionmaker(bind=db_engine)
    runtime.initialize()
    clock = datetime(2026, 10, 18, 9, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(runtime_module, "utcnow", lambda: clock)

    def admit(i):
        try:
            runtime.remember_nonce(f"concurrent-nonce-{i:04d}", "app-1")
            return 200
        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(admit, range(8)))
    assert sorted(results) == [200] * 3 + [429] * 5
    with runtime.sessions() as db:
        assert db.query(GatewayNonce).count() == 3
        assert db.query(GatewayRateLimit).one().requests == 3


def test_v2_upgrade_preserves_jobs_and_nonces(tmp_path):
    runtime = GatewayRuntime(config_for(tmp_path / "upgrade.db"))
    runtime.initialize()
    from app.integrations.contracts import DocumentRequest

    job = runtime.submit(DocumentRequest.model_validate(document()))
    runtime.remember_nonce("retained-nonce-000001")
    with runtime.engine.begin() as db:
        db.execute(text("DROP TABLE gateway_rate_limits"))
        db.execute(text("UPDATE gateway_schema_version SET version=2"))
    runtime.initialize()
    runtime.initialize()
    with runtime.sessions() as db:
        assert (
            db.get(GatewayJob, job.gateway_job_id).idempotency_key == document()["idempotency_key"]
        )
        assert db.get(GatewayNonce, "retained-nonce-000001")
        assert db.query(GatewayRateLimit).count() == 0
        assert db.scalar(text("SELECT version FROM gateway_schema_version")) == 3
    runtime.engine.dispose()


def test_gateway_security_errors_and_logs_exclude_private_values(tmp_path, caplog):
    app = create_app(config_for(tmp_path / "redaction.db"))
    private = "PRIVATE_EMPLOYEE_FREE_TEXT_20261018"
    with TestClient(app) as client:
        body = json.dumps({**document(), "reason": private}).encode()
        headers = signing.sign("app-1", APP_KEY, "POST", "/v1/documents", body)
        headers["Idempotency-Key"] = document()["idempotency_key"]
        headers["Content-Type"] = "application/json"
        responses = [
            client.post("/v1/documents", content=body + b" ", headers=headers),
            client.post("/v1/documents", content=body, headers=headers),
        ]
        assert [r.status_code for r in responses] == [401, 422]
        oversized = b"x" * 65537
        response = client.post(
            "/v1/documents",
            content=oversized,
            headers=signing.sign("app-1", APP_KEY, "POST", "/v1/documents", oversized),
        )
        assert response.status_code == 413
        output = caplog.text + "".join(r.text for r in responses) + response.text
        for marker in (APP_KEY, private, headers["X-Signature"]):
            assert marker not in output
        with app.state.runtime.sessions() as db:
            assert db.query(GatewayJob).count() == 0


def test_mock_environment_is_private_generated_and_never_overwritten(tmp_path):
    output = tmp_path / "private.env"
    command = [sys.executable, "-m", "app.gateway.configure_mock", "--output", str(output)]
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 0
    values = dotenv_values(output)
    assert output.stat().st_mode & 0o777 == 0o600
    assert values["COMPOSE_PROJECT_NAME"].startswith("janamen-mock-")
    assert len(values["DEMO_PASSWORD"]) >= 24 and values["DEMO_PASSWORD"] != "Password123!"
    assert values["GEMINI_DATA_SHARING_APPROVED"] == "false"
    for name in ("DEMO_PASSWORD", "SECRET_KEY", "INTEGRATION_OUTBOUND_KEY", "GATEWAY_CALLBACK_KEY"):
        assert values[name] not in first.stdout + first.stderr
    before = output.read_bytes()
    second = subprocess.run(command, capture_output=True, text=True)
    assert second.returncode != 0 and output.read_bytes() == before
    production_output = tmp_path / "production.env"
    production = subprocess.run(
        [*command[:-1], str(production_output)],
        env={**os.environ, "ENVIRONMENT": "production"},
        capture_output=True,
        text=True,
    )
    assert production.returncode != 0 and "production" in production.stderr
    assert not production_output.exists() and output.read_bytes() == before


def test_pending_demo_smoke_repeats_without_a_second_request_or_debit(
    client,
    db_session,
    monkeypatch,
):
    from app.config import settings
    from app.integrations.demo_smoke import run_smoke
    from app.models.integration import IntegrationOutbox
    from app.models.request import Request
    from app.provision_demo import provision_accounts

    monkeypatch.setattr(settings, "INTEGRATION_GATEWAY_URL", "http://synthetic.invalid")
    provision_accounts(db_session)
    first = run_smoke(client, "unit-pending", expect_pending=True)
    repeat = run_smoke(client, "unit-pending", expect_pending=True)
    assert first["request_code"] == repeat["request_code"]
    assert not first["reused_request"] and repeat["reused_request"]
    assert db_session.query(Request).filter_by(request_code=first["request_code"]).count() == 1
    assert db_session.query(IntegrationOutbox).count() == 1


def test_callback_audit_failure_is_atomic_and_retry_has_one_set_of_effects(
    client,
    db_session,
    employee_headers,
    manager_headers,
    connected,
    monkeypatch,
    caplog,
):
    from app.integrations import outbox
    from app.models.audit import AuditEvent
    from app.models.notification import Notification
    from app.models.request import Request, RequestEvent

    rid = approve_vacation(client, employee_headers, manager_headers)
    assert outbox.dispatch_one(db_session) and connected.process_one()
    event_count = db_session.query(RequestEvent).filter_by(request_id=rid).count()
    audit_count = db_session.query(AuditEvent).filter_by(action="INTEGRATION_REGISTERED").count()

    def fail_audit(*_args, **_kwargs):
        raise RuntimeError("PRIVATE_CALLBACK_AUDIT_MARKER")

    with monkeypatch.context() as patch:
        patch.setattr(outbox.audit_service, "log_event", fail_audit)
        assert connected.callback_one()
    db_session.expire_all()
    req = db_session.get(Request, rid)
    assert req.status.value == "Approved" and req.integration_status == "SENT"
    assert req.external_sync_id is None
    assert db_session.query(RequestEvent).filter_by(request_id=rid).count() == event_count
    assert db_session.query(Notification).filter_by(title="MOCK document registered").count() == 0
    assert "PRIVATE_CALLBACK_AUDIT_MARKER" not in caplog.text
    for _ in range(2):
        with connected.sessions() as db:
            job = db.query(GatewayJob).one()
            job.callback_status = "PENDING"
            job.callback_next_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        assert connected.callback_one()
    db_session.expire_all()
    assert db_session.get(Request, rid).integration_status == "REGISTERED"
    assert db_session.query(RequestEvent).filter_by(request_id=rid).count() == event_count + 1
    assert (
        db_session.query(AuditEvent).filter_by(action="INTEGRATION_REGISTERED").count()
        == audit_count + 1
    )
    assert db_session.query(Notification).filter_by(title="MOCK document registered").count() == 1
