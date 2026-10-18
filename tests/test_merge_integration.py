"""Compatibility of both deployed branches with the signed MOCK gateway."""

import os
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, create_engine, inspect, text
from sqlalchemy.exc import DataError, IntegrityError

from app.migrate import HEAD, upgrade_database
from app.models import Notification, Request
from app.models.enums import RequestStatus, RequestType
from app.models.integration import IntegrationOutbox
from tests.test_integration_gateway import connected, gateway_client

__all__ = ["connected", "gateway_client"]


@pytest.fixture
def upgrade_engine(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL", "")
    schema = "janamen_upgrade_" + uuid4().hex
    if url.startswith("postgresql"):
        owner = create_engine(url)
        with owner.begin() as db:
            db.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        engine = create_engine("sqlite:///" + str(tmp_path / "upgrade.db"))
    try:
        yield engine
    finally:
        engine.dispose()
        if url.startswith("postgresql"):
            with owner.begin() as db:
                db.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
            owner.dispose()


def at_revision(engine, revision):
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as db:
        cfg.attributes["connection"] = db
        command.upgrade(cfg, revision)


def insert_old_records(engine, has_profiles):
    now = datetime(2026, 10, 18, tzinfo=timezone.utc)
    with engine.begin() as db:
        tables = {
            name: Table(name, MetaData(), autoload_with=db)
            for name in [
                "users",
                "requests",
                "request_events",
                "audit_events",
                "integration_outbox",
            ]
        }
        db.execute(
            tables["users"]
            .insert()
            .values(
                id=1,
                email="synthetic@example.test",
                password_hash="unused",
                full_name="Synthetic upgrade fixture",
                role="EMPLOYEE",
                is_active=True,
                created_at=now,
            )
        )
        base = dict(
            user_id=1, start_date=now.date(), status="APPROVED", created_at=now, updated_at=now
        )
        db.execute(
            tables["requests"]
            .insert()
            .values(id=1, request_code="REQ-N000001", type="ADVANCE_PAYMENT", amount=99.01, **base)
        )
        if has_profiles:
            for rid, status in [(2, "PENDING"), (3, "APPROVED")]:
                db.execute(
                    tables["requests"]
                    .insert()
                    .values(
                        **{**base, "status": status},
                        id=rid,
                        request_code=f"REQ-N{rid:06d}",
                        type="PROFILE_UPDATE",
                        profile_changes={"location": {"from": "Synthetic A", "to": "Synthetic B"}},
                    )
                )
            # Main's ORM stored absent JSON as JSON null; preserve that representation.
            db.execute(
                tables["requests"]
                .insert()
                .values(
                    **base, id=4, request_code="REQ-N000004", type="VACATION", profile_changes=None
                )
            )
        db.execute(
            tables["request_events"]
            .insert()
            .values(id=1, request_id=1, actor_id=1, event_type="SUBMITTED", created_at=now)
        )
        db.execute(
            tables["audit_events"]
            .insert()
            .values(
                id=1,
                action="SYNTHETIC_UPGRADE",
                actor_id=1,
                target_type="request",
                target_id="REQ-N000001",
                created_at=now,
            )
        )
        job = dict(
            id=1,
            request_id=1,
            operation="ONE_C_ORDER",
            idempotency_key="REQ-N000001:v1",
            status="PENDING",
            attempts=0,
            next_attempt_at=now,
            created_at=now,
        )
        db.execute(tables["integration_outbox"].insert().values(**job))


def old_two_kind_guard(engine):
    # Emulate the CHECK/triggers already installed by the published 0009 revision.
    condition = "status IN ('PENDING','APPROVED','REJECTED') AND type IN ('VACATION','ADVANCE_PAYMENT') AND (end_date IS NULL OR end_date >= start_date) AND (amount IS NULL OR amount > 0) AND (charged_leave_days IS NULL OR charged_leave_days >= 0) AND ((type='VACATION' AND amount IS NULL) OR (type='ADVANCE_PAYMENT' AND amount IS NOT NULL AND end_date IS NULL))"
    with engine.begin() as db:
        if engine.dialect.name == "postgresql":
            db.exec_driver_sql("ALTER TABLE requests DROP CONSTRAINT ck_requests_domain")
            db.exec_driver_sql(
                "ALTER TABLE requests ADD CONSTRAINT ck_requests_domain CHECK (" + condition + ")"
            )
        else:
            for column in sorted(
                [c["name"] for c in inspect(db).get_columns("requests")], key=len, reverse=True
            ):
                condition = re.sub(r"\b" + column + r"\b", "NEW." + column, condition)
            for action in ["INSERT", "UPDATE"]:
                db.exec_driver_sql(f"DROP TRIGGER ck_requests_{action.lower()}")
                db.exec_driver_sql(
                    f"CREATE TRIGGER ck_requests_{action.lower()} BEFORE {action} ON requests WHEN NOT ({condition}) BEGIN SELECT RAISE(ABORT, 'Invalid domain values'); END"
                )


@pytest.mark.parametrize("starting", ["fresh", "0006_profile_updates", "0010_source_metadata"])
def test_both_deployed_histories_upgrade_without_losing_rows(upgrade_engine, starting):
    engine = upgrade_engine
    if starting != "fresh":
        at_revision(engine, starting)
        insert_old_records(engine, starting == "0006_profile_updates")
        if starting == "0010_source_metadata":
            old_two_kind_guard(engine)
    upgrade_database(engine)
    upgrade_database(engine)
    with engine.begin() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
        if starting == "fresh":
            return
        assert db.scalar(text("SELECT count(*) FROM request_events")) == 1
        assert db.scalar(text("SELECT count(*) FROM audit_events")) == 1
        assert db.scalar(text("SELECT idempotency_key FROM integration_outbox")) == "REQ-N000001:v1"
        assert Decimal(str(db.scalar(text("SELECT amount FROM requests WHERE id=1")))) == Decimal(
            "99.01"
        )
        if starting == "0006_profile_updates":
            assert db.scalar(text("SELECT count(*) FROM requests")) == 4
            assert (
                db.scalar(
                    text(
                        "SELECT count(*) FROM requests WHERE CAST(type AS VARCHAR)='PROFILE_UPDATE'"
                    )
                )
                == 2
            )
            assert db.scalar(text("SELECT status FROM integration_outbox")) == "DEAD"
        else:
            assert db.scalar(text("SELECT count(*) FROM requests")) == 1
        # Test the new type after the complete transactional upgrade has committed.
        db.execute(
            text(
                "UPDATE requests SET type='PROFILE_UPDATE',amount=NULL,profile_changes=:changes WHERE id=1"
            ),
            {"changes": '{"location":{"from":"Synthetic A","to":"Synthetic B"}}'},
        )
    with engine.begin() as db:
        with pytest.raises((IntegrityError, DataError)):
            db.execute(text("UPDATE requests SET amount=-1 WHERE id=1"))


def legacy_profile_change(client, headers, db_session, field, value):
    """A pending contact change saved before the profile became read-only (deployed data)."""
    profile = client.get("/api/v1/me/profile", headers={**headers, "Accept-Language": "en"}).json()
    req = Request(
        request_code=f"REQ-L{uuid4().hex[:6].upper()}",
        user_id=profile["user_id"],
        type=RequestType.PROFILE_UPDATE,
        start_date=datetime.now(timezone.utc).date(),
        status=RequestStatus.PENDING,
        profile_changes={field: {"from": profile[field], "to": value}},
    )
    db_session.add(req)
    db_session.commit()
    return req.id


def test_profile_submissions_are_refused_with_gateway_enabled(
    client, employee_headers, db_session, connected
):
    headers = {**employee_headers, "Idempotency-Key": "profile-merge-submission-001"}
    payload = {
        "type": "Profile update",
        "profile_changes": {"location": "Synthetic updated location"},
    }
    before = db_session.query(Notification).count()
    for _ in range(2):
        assert client.post("/api/v1/requests", headers=headers, json=payload).status_code == 409
    assert db_session.query(Notification).count() == before
    assert db_session.query(IntegrationOutbox).count() == 0


def test_legacy_profile_approval_stays_local_and_applies(
    client, employee_headers, manager_headers, db_session, connected
):
    rid = legacy_profile_change(
        client, employee_headers, db_session, "location", "Synthetic updated location"
    )
    approved = client.post(f"/api/v1/requests/{rid}/approve", headers=manager_headers)
    assert approved.status_code == 200 and approved.json()["sync_status"] == "NOT_REQUIRED"
    assert db_session.query(IntegrationOutbox).count() == 0
    assert (
        client.get("/api/v1/me/profile", headers=employee_headers).json()["location"]
        == "Synthetic updated location"
    )


def test_profile_approval_rollback_keeps_contacts_unchanged(
    client, employee_headers, manager_headers, db_session, connected, monkeypatch
):
    from app.services.notification_service import notification_service

    before = client.get("/api/v1/me/profile", headers=employee_headers).json()
    rid = legacy_profile_change(
        client, employee_headers, db_session, "location", "Synthetic rollback place"
    )

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic notification failure")

    monkeypatch.setattr(notification_service, "create_notification", fail)
    assert (
        client.post(f"/api/v1/requests/{rid}/approve", headers=manager_headers).status_code == 500
    )
    after = client.get("/api/v1/me/profile", headers=employee_headers).json()
    assert (
        after["location"] == before["location"]
        and after["leave_balance_days"] == before["leave_balance_days"]
    )
    db_session.expire_all()
    assert db_session.get(Request, rid).status.value == "Pending"
    assert db_session.query(IntegrationOutbox).count() == 0


def test_submission_hash_matches_the_previous_deployed_contract(
    client, employee_headers, db_session
):
    headers = {**employee_headers, "Idempotency-Key": "legacy-submission-key-001"}
    payload = {"type": "Advance payment", "start_date": "2026-12-01", "amount": 100}
    first = client.post("/api/v1/requests", headers=headers, json=payload)
    assert first.status_code == 201
    row = db_session.get(Request, first.json()["id"])
    # Frozen hash from the pre-merge payload schema, before profile_changes existed.
    assert row.submission_hash == "c63028d080374e913d1256b29fa187def427ae0e681e026f04bdec7cd508356e"
    assert client.post("/api/v1/requests", headers=headers, json=payload).json()["id"] == row.id


def test_contact_change_review_visibility_is_explicit_and_scoped(
    client, employee_headers, manager_headers, hr_admin_headers, db_session
):
    rid = legacy_profile_change(
        client, employee_headers, db_session, "emergency_contact", "Synthetic review contact"
    )
    req = {"id": rid}
    owner = client.get("/api/v1/me/profile", headers=employee_headers).json()["user_id"]
    manager = client.get(f"/api/v1/manager/team/{owner}", headers=manager_headers).json()
    assert manager["emergency_contact"] is None  # current-profile projection remains HR-only
    change = next(r for r in manager["requests"] if r["id"] == req["id"])
    assert change["profile_changes"]["emergency_contact"]["to"] == "Synthetic review contact"
    # An unrelated employee still cannot inspect that approval/history projection.
    assert client.get(f"/api/v1/manager/team/{owner}", headers=employee_headers).status_code == 403
