"""Behavioral acceptance checks for the remaining QA fix plan."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.gateway.models import GatewayJob, MockDocument
from app.gateway.runtime import status_for
from app.integrations import outbox, profile_sync
from app.integrations.contracts import RegistrationResult
from app.models import Notification, Request, RequestEvent
from app.models.integration import IntegrationOutbox
from app.models.profile import EmployeeProfile
from tests.test_integration_gateway import approve_vacation, connected, gateway_client


def test_submission_retry_is_employee_scoped_and_immutable(
    client, employee_headers, manager_headers, db_session
):
    payload = {"type": "Advance payment", "start_date": "2026-12-01", "amount": 100}
    key = {"Idempotency-Key": "submission-test-0001"}
    first = client.post("/api/v1/requests", headers={**employee_headers, **key}, json=payload)
    assert first.status_code == 201
    before = db_session.query(Notification).count()
    repeat = client.post("/api/v1/requests", headers={**employee_headers, **key}, json=payload)
    assert repeat.status_code == 201 and repeat.json()["id"] == first.json()["id"]
    assert db_session.query(Notification).count() == before
    assert db_session.query(RequestEvent).filter_by(request_id=first.json()["id"]).count() == 1
    changed = client.post(
        "/api/v1/requests", headers={**employee_headers, **key}, json={**payload, "amount": 200}
    )
    assert changed.status_code == 409
    other = client.post("/api/v1/requests", headers={**manager_headers, **key}, json=payload)
    assert other.status_code == 201 and other.json()["id"] != first.json()["id"]


def test_concurrent_submission_retries_create_one_request(client, employee_headers, db_session):
    def send(_):
        return client.post(
            "/api/v1/requests",
            headers={**employee_headers, "Idempotency-Key": "concurrent-submission-0001"},
            json={"type": "Advance payment", "start_date": "2026-12-01", "amount": 100},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(send, range(2)))
    assert [r.status_code for r in rows] == [201, 201]
    assert len({r.json()["id"] for r in rows}) == 1
    assert (
        db_session.query(Request).filter_by(submission_key="concurrent-submission-0001").count()
        == 1
    )


__all__ = ["connected", "gateway_client"]


def test_hr_recovery_preserves_document_key_and_rejects_old_callbacks(
    client, db_session, employee_headers, manager_headers, hr_admin_headers, connected
):
    rid = approve_vacation(client, employee_headers, manager_headers)
    assert outbox.dispatch_one(db_session)
    with connected.sessions() as session:
        job = session.query(GatewayJob).one()
        job.status, job.error_code, job.attempts = "DEAD", "DOCUMENTOLOG_UNAVAILABLE", 8
        job.callback_status, job.callback_next_at = "PENDING", datetime.now(timezone.utc)
        session.commit()
        old = status_for(job)
    assert connected.callback_one()
    task = db_session.query(IntegrationOutbox).one()
    db_session.refresh(task)
    url = f"/api/v1/admin/integrations/queue/{task.id}/retry"
    payload = {"expected_retry_count": 0, "reason": "Temporary outage resolved"}
    for headers in [employee_headers, manager_headers]:
        assert client.post(url, headers=headers, json=payload).status_code == 403
    assert client.post(url, headers=hr_admin_headers, json=payload).status_code == 200
    assert client.post(url, headers=hr_admin_headers, json=payload).status_code == 409
    # A duplicate DEAD result in the queue-to-dispatch window cannot cancel recovery.
    assert (
        connected.send_callback(
            RegistrationResult(**old.model_dump(), nonce="before-dispatch-callback")
        )
        == 409
    )
    assert outbox.dispatch_one(db_session)
    db_session.expire_all()
    task = db_session.get(IntegrationOutbox, task.id)
    assert task.gateway_job_id == old.gateway_job_id and task.recovery_key
    assert (
        connected.send_callback(
            RegistrationResult(**old.model_dump(), nonce="superseded-callback-0001")
        )
        == 409
    )
    assert connected.process_one() and connected.callback_one()
    db_session.expire_all()
    assert db_session.get(Request, rid).integration_status == "REGISTERED"
    assert db_session.query(Notification).filter_by(title="MOCK document registered").count() == 1
    with connected.sessions() as session:
        assert session.query(GatewayJob).count() == session.query(MockDocument).count() == 1


def test_known_missing_gateway_job_is_not_blindly_resubmitted(
    client, db_session, employee_headers, manager_headers, hr_admin_headers, connected
):
    approve_vacation(client, employee_headers, manager_headers)
    outbox.dispatch_one(db_session)
    task = db_session.query(IntegrationOutbox).one()
    task.status = "DEAD"
    db_session.commit()
    assert (
        client.post(
            f"/api/v1/admin/integrations/queue/{task.id}/retry",
            headers=hr_admin_headers,
            json={"expected_retry_count": 0, "reason": "Investigate outage"},
        ).status_code
        == 200
    )
    calls = []
    outbox.dispatch_one(
        db_session, send=lambda *args: calls.append(args), get=lambda path: (404, {})
    )
    assert calls == []
    db_session.refresh(task)
    assert task.status == "FAILED"


def test_two_outbox_workers_create_one_gateway_document(
    client, db_session, employee_headers, manager_headers, connected
):
    approve_vacation(client, employee_headers, manager_headers)
    factory = sessionmaker(bind=db_session.get_bind())

    def dispatch(_):
        with factory() as session:
            return outbox.dispatch_one(session)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(dispatch, range(2)))
    assert connected.process_one()
    with connected.sessions() as session:
        assert session.query(GatewayJob).count() == session.query(MockDocument).count() == 1


def test_hr_explicitly_resolves_employee_codes_without_creating_accounts(
    client, db_session, hr_admin_headers, employee_headers, connected
):
    profile_sync.sync_profiles(db_session, force=True)
    rows = client.get("/api/v1/admin/integrations/reviews", headers=hr_admin_headers).json()
    before = db_session.query(EmployeeProfile).count()
    for code, user_id in [("DEMO-MGR-001", 1), ("DEMO-EMP-001", 3)]:
        review = next(r for r in rows if r["employee_code"] == code)
        url = f"/api/v1/admin/integrations/reviews/{code}/resolve"
        body = {
            "observed_at": review["observed_at"],
            "user_id": user_id,
            "reason": "Verified synthetic employee code",
        }
        assert client.post(url, headers=employee_headers, json=body).status_code == 403
        assert client.post(url, headers=hr_admin_headers, json=body).status_code == 200
        assert client.post(url, headers=hr_admin_headers, json=body).status_code == 404
    db_session.expire_all()
    assert db_session.query(EmployeeProfile).count() == before
    assert (
        db_session.query(EmployeeProfile).filter_by(user_id=3).one().employee_code == "DEMO-EMP-001"
    )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE employee_profiles SET leave_balance_days=-1 WHERE user_id=3",
        "UPDATE requests SET status='UNKNOWN' WHERE id=1",
        "UPDATE requests SET end_date='1900-01-01' WHERE id=1",
        "UPDATE requests SET amount=-1 WHERE id=1",
    ],
)
def test_database_rejects_invalid_direct_writes(db_engine, statement):
    with db_engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(text(statement))


def test_normal_reconciliation_does_not_recreate_lost_accepted_jobs(
    client, db_session, employee_headers, manager_headers, connected
):
    approve_vacation(client, employee_headers, manager_headers)
    assert outbox.dispatch_one(db_session)
    task = db_session.query(IntegrationOutbox).one()
    task.next_attempt_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    db_session.commit()
    calls = []
    assert outbox.dispatch_one(
        db_session, get=lambda path: (404, {}), send=lambda *args: calls.append(args)
    )
    assert not outbox.dispatch_one(db_session, send=lambda *args: calls.append(args))
    db_session.refresh(task)
    assert task.status == "FAILED" and task.last_error == "JOB_NOT_FOUND" and not calls


def test_hr_recovery_reconciles_remote_success_after_local_transport_failure(
    client, db_session, employee_headers, manager_headers, hr_admin_headers, connected
):
    rid = approve_vacation(client, employee_headers, manager_headers)
    assert outbox.dispatch_one(db_session)
    assert connected.process_one()
    task = db_session.query(IntegrationOutbox).one()
    task.status, task.last_error = "FAILED", "HTTP_401"
    task.request.integration_status = "FAILED"
    db_session.commit()
    assert (
        client.post(
            f"/api/v1/admin/integrations/queue/{task.id}/retry",
            headers=hr_admin_headers,
            json={"expected_retry_count": 0, "reason": "Transport credentials corrected"},
        ).status_code
        == 200
    )
    assert outbox.dispatch_one(db_session)
    db_session.expire_all()
    assert db_session.get(Request, rid).integration_status == "REGISTERED"
    assert db_session.query(Notification).filter_by(title="MOCK document registered").count() == 1
    with connected.sessions() as db:
        assert db.query(GatewayJob).count() == db.query(MockDocument).count() == 1
