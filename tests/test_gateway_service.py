"""Persistent MOCK gateway contract/security tests. No enterprise network calls."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.gateway.config import GatewaySettings
from app.gateway.main import create_app
from app.gateway.models import GatewayJob, MockDocument
from app.integrations import signing

APP_KEY = "synthetic-app-gateway-key-" + "a" * 32
CALLBACK_KEY = "synthetic-callback-key-" + "b" * 32


def config_for(path):
    return GatewaySettings(
        DATABASE_URL="sqlite:///" + str(path),
        APP_KEY_ID="app-1",
        APP_KEY=APP_KEY,
        CALLBACK_KEY_ID="gw-1",
        CALLBACK_KEY=CALLBACK_KEY,
        WORKER_ENABLED=False,
    )


@pytest.fixture
def gateway_client(tmp_path):
    app = create_app(config_for(tmp_path / "gateway.db"))
    with TestClient(app) as client:
        yield client


def document(code="REQ-N000005"):
    return {
        "idempotency_key": code + ":v1",
        "kind": "VACATION_REQUEST",
        "request_code": code,
        "employee_code": "JP-10428",
        "period": {"start": "2026-11-23", "end": "2026-11-25", "days": 3},
        "approved_by_employee_code": "JP-10201",
        "approved_at": "2026-10-17T10:15:00Z",
    }


def signed(client, method, path, data=None, *, key=APP_KEY, now=None):
    body = json.dumps(data).encode() if data is not None else b""
    headers = signing.sign("app-1", key, method, path, body, now=now)
    headers["Content-Type"] = "application/json"
    if data and "idempotency_key" in data:
        headers["Idempotency-Key"] = data["idempotency_key"]
    return client.request(method, path, content=body, headers=headers)


def test_valid_tampered_old_unknown_retired_and_replayed_signatures(gateway_client):
    c = gateway_client
    body = json.dumps(document()).encode()
    headers = signing.sign("app-1", APP_KEY, "POST", "/v1/documents", body)
    headers["Idempotency-Key"] = document()["idempotency_key"]
    headers["Content-Type"] = "application/json"
    response = c.post("/v1/documents", content=body, headers=headers)
    assert response.status_code == 202
    assert c.post("/v1/documents", content=body, headers=headers).status_code == 401
    assert signed(c, "POST", "/v1/documents", document(), key="wrong" * 16).status_code == 401
    assert signed(c, "POST", "/v1/documents", document(), now=time.time() - 301).status_code == 401
    assert signed(c, "POST", "/v1/documents", document(), now=time.time() + 301).status_code == 401
    bad = signing.sign("retired-key", APP_KEY, "GET", "/health", b"")
    assert c.get("/health", headers=bad).status_code == 401
    c.app.state.runtime.config.JANAMEN_KEYS["previous"] = APP_KEY
    previous = signing.sign("previous", APP_KEY, "GET", "/health", b"")
    assert c.get("/health", headers=previous).status_code == 200
    del c.app.state.runtime.config.JANAMEN_KEYS["previous"]
    assert (
        c.get(
            "/health", headers=signing.sign("previous", APP_KEY, "GET", "/health", b"")
        ).status_code
        == 401
    )
    assert (
        c.post(
            "/v1/documents",
            content=body + b" ",
            headers=signing.sign("app-1", APP_KEY, "POST", "/v1/documents", body),
        ).status_code
        == 401
    )


def test_all_gateway_endpoints_reject_employee_bearer(gateway_client, employee_headers):
    for method, path in [
        ("GET", "/health"),
        ("GET", "/v1/employees"),
        ("GET", "/v1/employees/JP-10428"),
        ("GET", "/v1/documents/REQ-N000005:v1"),
        ("POST", "/v1/documents"),
        ("GET", "/docs"),
    ]:
        assert gateway_client.request(method, path, headers=employee_headers).status_code == 401


def test_idempotency_persists_and_rejects_changed_body(gateway_client):
    a = signed(gateway_client, "POST", "/v1/documents", document())
    b = signed(gateway_client, "POST", "/v1/documents", document())
    assert a.status_code == b.status_code == 202
    assert a.json()["gateway_job_id"] == b.json()["gateway_job_id"]
    changed = document()
    changed["period"]["days"] = 2
    assert signed(gateway_client, "POST", "/v1/documents", changed).status_code == 409
    runtime = gateway_client.app.state.runtime
    assert runtime.process_one()
    assert not runtime.process_one()
    assert (
        signed(gateway_client, "POST", "/v1/documents", document()).json()["status"] == "REGISTERED"
    )
    with runtime.sessions() as db:
        assert db.query(GatewayJob).count() == db.query(MockDocument).count() == 1


def test_concurrent_same_key_creates_one_job_and_document(gateway_client):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: signed(gateway_client, "POST", "/v1/documents", document()), range(4)
            )
        )
    assert {r.status_code for r in results} == {202}
    assert len({r.json()["gateway_job_id"] for r in results}) == 1
    runtime = gateway_client.app.state.runtime
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: runtime.process_one(), range(2)))
    with runtime.sessions() as db:
        assert db.query(MockDocument).count() == 1


def test_gateway_restart_recovers_jobs_and_nonces(tmp_path):
    config = config_for(tmp_path / "restart.db")
    app = create_app(config)
    replay = signing.sign("app-1", APP_KEY, "GET", "/health", b"")
    with TestClient(app) as first:
        assert first.get("/health", headers=replay).status_code == 200
        job_id = signed(first, "POST", "/v1/documents", document()).json()["gateway_job_id"]
        with app.state.runtime.sessions() as db:
            job = db.get(GatewayJob, job_id)
            job.status = "PROCESSING"
            job.lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
            job.lease_token = uuid4().hex
            db.commit()
    restarted = create_app(config)
    with TestClient(restarted) as second:
        assert second.get("/health", headers=replay).status_code == 401
        assert restarted.state.runtime.process_one()
        status = signed(second, "GET", "/v1/documents/REQ-N000005:v1").json()
        assert status["status"] == "REGISTERED" and status["external_ref"].startswith("MOCK-DOC-")
        assert (
            signed(second, "POST", "/v1/documents", document()).json()["gateway_job_id"] == job_id
        )
        with restarted.state.runtime.sessions() as db:
            assert db.query(MockDocument).count() == 1


def test_callback_retry_is_persistent_and_never_registers_twice(gateway_client, monkeypatch):
    runtime = gateway_client.app.state.runtime
    signed(gateway_client, "POST", "/v1/documents", document())
    runtime.process_one()
    monkeypatch.setattr(runtime, "send_callback", lambda _: 503)
    assert runtime.callback_one()
    with runtime.sessions() as db:
        job = db.query(GatewayJob).one()
        assert job.status == "REGISTERED" and job.callback_status == "PENDING"
        job.callback_next_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    monkeypatch.setattr(runtime, "send_callback", lambda _: 200)
    assert runtime.callback_one()
    with runtime.sessions() as db:
        assert db.query(GatewayJob).one().callback_status == "DELIVERED"
        assert db.query(MockDocument).count() == 1


def test_query_string_is_signed_and_mock_snapshots_are_canonical(gateway_client):
    path = "/v1/employees?updated_since=2026-10-17T08%3A00%3A00Z"
    good = signed(gateway_client, "GET", path)
    assert good.status_code == 200 and good.json()["mode"] == "MOCK"
    assert all(row["full_name"].startswith("Synthetic") for row in good.json()["employees"])
    headers = signing.sign("app-1", APP_KEY, "GET", "/v1/employees", b"")
    assert gateway_client.get(path, headers=headers).status_code == 401
    assert signed(gateway_client, "GET", "/v1/employees/JP-10428").status_code == 200
    empty = signed(gateway_client, "GET", "/v1/employees?updated_since=2027-01-01T00%3A00%3A00Z")
    assert empty.json()["employees"] == []


def test_canonical_validation_does_not_echo_payload(gateway_client):
    bad = document()
    bad["reason"] = "PRIVATE-MARKER-MUST-NOT-ECHO"
    response = signed(gateway_client, "POST", "/v1/documents", bad)
    assert response.status_code == 422 and "PRIVATE-MARKER" not in response.text
    advance = document("REQ-N000006")
    advance.pop("period")
    advance.update(kind="ADVANCE_PAYMENT_REQUEST", amount="100.10", currency="KZT")
    assert signed(gateway_client, "POST", "/v1/documents", advance).status_code == 202


def test_mock_connector_temporary_failure_reaches_dead_without_document(gateway_client):
    runtime = gateway_client.app.state.runtime
    runtime.config.MOCK_DOCUMENTOLOG_FAILURE = "temporary"
    signed(gateway_client, "POST", "/v1/documents", document())
    for attempt in range(1, 9):
        assert runtime.process_one()
        with runtime.sessions() as db:
            job = db.query(GatewayJob).one()
            assert job.attempts == attempt
            if attempt < 8:
                assert job.status == "PENDING"
                job.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                db.commit()
    with runtime.sessions() as db:
        assert db.query(GatewayJob).one().status == "DEAD"
        assert db.query(MockDocument).count() == 0


def test_invalid_key_errors_hide_input_values():
    marker = "SECRET_MARKER"
    with pytest.raises(ValueError) as error:
        GatewaySettings(JANAMEN_KEYS={"broken": marker})
    assert marker not in str(error.value)
