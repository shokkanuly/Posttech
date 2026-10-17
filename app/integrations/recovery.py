"""HR recovery commands: durable intent, immutable document keys, explicit mapping."""

from datetime import datetime, timezone
from urllib.parse import quote
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import update

from app.config import settings
from app.integrations.contracts import EmployeeSnapshot
from app.integrations.outbox import aware, gateway_request
from app.integrations.profile_sync import apply_snapshot
from app.models.enums import RequestStatus
from app.models.integration import IntegrationOutbox, IntegrationReview
from app.models.profile import EmployeeProfile
from app.services.audit_service import audit_service


def can_retry(task):
    return bool(
        settings.INTEGRATION_GATEWAY_URL
        and task.operation == "REGISTER_DOCUMENT"
        and task.payload
        and task.request.status == RequestStatus.APPROVED
        and task.last_error not in {"INVALID_CONTRACT", "LEGACY_CONTRACT", "JOB_NOT_FOUND"}
        and not (task.last_error or "").startswith("DOCUMENTOLOG_REJECT")
    )


def queue_retry(db, task_id, expected, actor, reason):
    task = db.get(IntegrationOutbox, task_id)
    if not settings.INTEGRATION_GATEWAY_URL:
        raise HTTPException(409, "Integration gateway is disabled")
    if task is None:
        raise HTTPException(404, "Integration task not found")
    if not can_retry(task):
        raise HTTPException(409, "This task requires operator correction, not replay")
    if task.request.status != RequestStatus.APPROVED:
        raise HTTPException(409, "Only approved requests can be recovered")
    changed = db.execute(
        update(IntegrationOutbox)
        .where(
            IntegrationOutbox.id == task_id,
            IntegrationOutbox.status.in_(["FAILED", "DEAD"]),
            IntegrationOutbox.retry_count == expected,
        )
        .values(
            status="PENDING",
            attempts=0,
            retry_count=expected + 1,
            retry_key=uuid4().hex,
            next_attempt_at=datetime.now(timezone.utc),
            last_error=None,
        ),
        execution_options={"synchronize_session": False},
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "Recovery state changed; reload the queue")
    audit_service.log_event(
        db,
        action="INTEGRATION_RETRY_REQUESTED",
        actor_id=actor.id,
        target_type="request",
        target_id=task.request.request_code,
        details={"reason": reason, "retry_count": expected + 1},
    )
    db.commit()
    return {"status": "queued", "retry_count": expected + 1}


def resolve_review(db, code, payload, actor):
    row = db.query(IntegrationReview).filter_by(employee_code=code).with_for_update().first()
    if row is None:
        raise HTTPException(404, "Review not found")
    if aware(row.observed_at) != payload.observed_at:
        raise HTTPException(409, "Review changed; reload before resolving")
    claimed = db.execute(
        update(IntegrationReview)
        .where(
            IntegrationReview.employee_code == code,
            IntegrationReview.observed_at == payload.observed_at,
        )
        .values(observed_at=datetime.now(timezone.utc)),
        execution_options={"synchronize_session": False},
    )
    if claimed.rowcount != 1:
        raise HTTPException(409, "Review changed; reload before resolving")
    response, data = gateway_request("GET", "/v1/employees/" + quote(code, safe=""))
    if response != 200:
        raise HTTPException(503, "Snapshot unavailable; review retained")
    try:
        snapshot = EmployeeSnapshot.model_validate(data)
    except ValidationError:
        raise HTTPException(503, "Invalid gateway snapshot; review retained") from None
    if snapshot.employee_code != code:
        raise HTTPException(409, "Snapshot code mismatch")
    old_code = None
    if payload.user_id is not None:
        profile = (
            db.query(EmployeeProfile).filter_by(user_id=payload.user_id).with_for_update().first()
        )
        if profile is None or not profile.user.is_active:
            raise HTTPException(409, "An active existing employee profile is required")
        other = db.query(EmployeeProfile).filter_by(employee_code=code).first()
        if other and other.user_id != payload.user_id:
            raise HTTPException(409, "Employee code already belongs to another account")
        old_code = profile.employee_code
        profile.employee_code = code
        db.flush()
    if not apply_snapshot(db, snapshot, "MOCK"):
        raise HTTPException(
            409, "Snapshot still conflicts; resolve source or manager mapping first"
        )
    audit_service.log_event(
        db,
        action="INTEGRATION_REVIEW_RESOLVED",
        actor_id=actor.id,
        target_type="employee_code",
        target_id=code,
        details={"reason": payload.reason, "previous_code": old_code, "user_id": payload.user_id},
    )
    db.commit()
    return {"status": "resolved", "employee_code": code, "mode": "MOCK"}
