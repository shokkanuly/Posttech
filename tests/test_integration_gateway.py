"""Integration gateway foundation: signatures, transactional outbox, worker, callbacks."""

import json
import time
from datetime import datetime, timedelta, timezone

import pytest
from starlette.datastructures import Headers

from app.config import Settings, settings
from app.integrations import outbox, signing
from app.models.integration import IntegrationOutbox
from app.models.notification import Notification
from app.models.request import Request

KEY = "synthetic-gateway-key-" + "k" * 32
STATUS_PATH = "/api/v1/internal/integrations/documentolog/status"


@pytest.fixture
def gateway(monkeypatch):
    monkeypatch.setattr(settings, "INTEGRATION_GATEWAY_URL", "https://gateway.test")
    monkeypatch.setattr(settings, "INTEGRATION_INBOUND_KEYS", {"gw-1": KEY})


def approve_vacation(client, employee_headers, manager_headers):
    created = client.post(
        "/api/v1/requests",
        json={"type": "Vacation", "start_date": "2026-12-01", "end_date": "2026-12-02"},
        headers=employee_headers,
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    approved = client.post(f"/api/v1/requests/{request_id}/approve", headers=manager_headers)
    assert approved.status_code == 200, approved.text
    return request_id


def signed_callback(client, payload, key=KEY):
    body = json.dumps(payload).encode()
    headers = signing.sign("gw-1", key, "POST", STATUS_PATH, body)
    return client.post(STATUS_PATH, content=body, headers=headers), headers, body


def test_signature_rejects_tampering_staleness_and_unknown_keys():
    body = b'{"a":1}'
    headers = Headers(signing.sign("gw-1", KEY, "POST", "/p", body))
    keys = {"gw-1": KEY}
    assert signing.verify(headers, keys, "POST", "/p", body) == headers["x-nonce"]
    for wrong in (
        (keys, "POST", "/p", b'{"a":2}'),
        (keys, "POST", "/other", body),
        ({"gw-2": KEY}, "POST", "/p", body),
    ):
        with pytest.raises(signing.SignatureError):
            signing.verify(headers, *wrong)
    with pytest.raises(signing.SignatureError):
        signing.verify(headers, keys, "POST", "/p", body, now=time.time() + 301)


def test_short_integration_keys_are_refused():
    with pytest.raises(ValueError, match="at least 32"):
        Settings(INTEGRATION_INBOUND_KEYS={"gw-1": "short"})


def test_without_gateway_approval_queues_nothing(
    client, db_session, employee_headers, manager_headers
):
    request_id = approve_vacation(client, employee_headers, manager_headers)
    assert db_session.query(IntegrationOutbox).count() == 0
    assert db_session.get(Request, request_id).integration_status is None


def test_approval_is_delivered_through_signing(
    client, db_session, gateway, employee_headers, manager_headers
):
    request_id = approve_vacation(client, employee_headers, manager_headers)
    sent = []

    def gateway_accepts(path, body, idempotency_key):
        sent.append((path, json.loads(body), idempotency_key))
        return 201, {"external_id": "1C-ORDER-77"}

    assert outbox.dispatch_one(db_session, gateway_accepts)
    assert outbox.dispatch_one(db_session, gateway_accepts)
    assert not outbox.dispatch_one(db_session, gateway_accepts)
    code = db_session.get(Request, request_id).request_code
    assert [(path, key) for path, _, key in sent] == [
        ("/v1/1c/orders", f"{code}:1c-order"),
        ("/v1/documentolog/documents", f"{code}:doclog"),
    ]
    assert set(sent[0][1]) == {
        "request_code",
        "employee_code",
        "type",
        "start_date",
        "end_date",
        "amount",
        "approver_employee_code",
    }
    assert sent[1][1] == {"request_code": code, "one_c_document_id": "1C-ORDER-77"}

    response, headers, body = signed_callback(client, {"request_code": code, "status": "SIGNED"})
    assert response.status_code == 200 and response.json() == {"applied": True}
    # The exact signed request cannot be replayed; a fresh duplicate report changes nothing.
    assert client.post(STATUS_PATH, content=body, headers=headers).status_code == 401
    duplicate, _, _ = signed_callback(client, {"request_code": code, "status": "SIGN_REJECTED"})
    assert duplicate.json() == {"applied": False}

    detail = client.get(f"/api/v1/requests/{request_id}", headers=employee_headers).json()
    assert detail["external_sync_id"] == "1C-ORDER-77"
    assert {
        "1C:ZUP created the order",
        "Order sent to Documentolog for signing",
        "Order signed in Documentolog",
    } <= {event["comment"] for event in detail["events"]}
    db_session.expire_all()
    assert db_session.get(Request, request_id).integration_status == "SIGNED"
    assert db_session.query(Notification).filter(Notification.title == "Order signed").count() == 1


def test_transient_failures_back_off_then_park_as_dead(
    client, db_session, gateway, employee_headers, manager_headers
):
    approve_vacation(client, employee_headers, manager_headers)

    def unavailable(*_):
        return 503, {}

    for attempt in range(1, 9):
        assert outbox.dispatch_one(db_session, unavailable)
        task = db_session.query(IntegrationOutbox).one()
        if attempt < 8:
            assert (task.status, task.attempts) == ("PENDING", attempt)
            assert not outbox.dispatch_one(db_session, unavailable)  # backoff: not due yet
            task.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db_session.commit()
    assert (task.status, task.last_error) == ("DEAD", "HTTP_503")
    failed = db_session.query(Notification).filter(
        Notification.title == "Integration delivery failed"
    )
    assert failed.count() >= 1


def test_data_errors_park_as_dead_without_retry(
    client, db_session, gateway, employee_headers, manager_headers
):
    approve_vacation(client, employee_headers, manager_headers)
    assert outbox.dispatch_one(db_session, lambda *_: (400, {}))
    task = db_session.query(IntegrationOutbox).one()
    assert (task.status, task.attempts, task.last_error) == ("DEAD", 1, "HTTP_400")


def test_unsigned_stale_and_foreign_callbacks_are_rejected(client, gateway):
    body = b'{"request_code":"REQ-N000001","status":"SIGNED"}'
    stale = signing.sign("gw-1", KEY, "POST", STATUS_PATH, body, now=time.time() - 400)
    foreign = signing.sign("gw-1", "x" * 40, "POST", STATUS_PATH, body)
    for headers in ({}, stale, foreign):
        assert client.post(STATUS_PATH, content=body, headers=headers).status_code == 401
