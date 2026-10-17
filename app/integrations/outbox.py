"""Transactional delivery of our canonical contract; never calls vendor APIs.

INTEGRATION_GATEWAY_URL is the switch. Approval and the immutable outbound snapshot
commit together. Network delivery and reconciliation happen only in this CLI worker.
"""

import random
import ssl
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import lru_cache
from typing import cast
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import or_, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from app.config import settings
from app.integrations import signing
from app.integrations.contracts import BACKOFF_SECONDS, DocumentRequest, JobStatus
from app.models.enums import (
    NotificationType,
    RequestEventType,
    RequestStatus,
    RequestType,
    UserRole,
)
from app.models.integration import IntegrationOutbox
from app.models.notification import Notification
from app.models.request import Request, RequestEvent
from app.models.user import User
from app.services.audit_service import audit_service
from app.services.notification_service import notification_service

Send = Callable[[str, bytes, str], tuple[int, dict]]
Get = Callable[[str], tuple[int, dict]]


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def enqueue(db: Session, req: Request) -> None:
    """Snapshot minimal canonical data now so retries never change the signed content."""
    employee = req.user.profile
    approver = req.reviewer.profile if req.reviewer else None
    data: dict = {
        "idempotency_key": f"{req.request_code}:v1",
        "request_code": req.request_code,
        "employee_code": employee.employee_code if employee else "",
        "approved_by_employee_code": approver.employee_code if approver else "",
        "approved_at": aware(req.updated_at).isoformat(),
        "kind": "VACATION_REQUEST"
        if req.type == RequestType.VACATION
        else "ADVANCE_PAYMENT_REQUEST",
    }
    if req.type == RequestType.VACATION:
        data["period"] = {
            "start": req.start_date.isoformat(),
            "end": (req.end_date or req.start_date).isoformat(),
            "days": req.charged_leave_days,
        }
    else:
        data["amount"], data["currency"] = str(Decimal(str(req.amount))), "KZT"
    db.add(
        IntegrationOutbox(
            request_id=req.id,
            operation="REGISTER_DOCUMENT",
            idempotency_key=data["idempotency_key"],
            payload=data,
            status="PENDING",
            attempts=0,
            next_attempt_at=datetime.now(timezone.utc),
        )
    )


@lru_cache(maxsize=1)
def _tls() -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=settings.INTEGRATION_TLS_CA or None)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    if settings.INTEGRATION_TLS_CERT:
        context.load_cert_chain(settings.INTEGRATION_TLS_CERT, settings.INTEGRATION_TLS_KEY or None)
    return context


def gateway_request(
    method: str, path: str, body: bytes = b"", key: str | None = None
) -> tuple[int, dict]:
    if not settings.INTEGRATION_GATEWAY_URL:
        return 0, {}
    base = settings.INTEGRATION_GATEWAY_URL.rstrip("/")
    headers = signing.sign(
        settings.INTEGRATION_OUTBOUND_KEY_ID,
        settings.INTEGRATION_OUTBOUND_KEY,
        method,
        urlsplit(base).path + path,
        body,
    )
    headers["Content-Type"] = "application/json"
    if key:
        headers["Idempotency-Key"] = key
    try:
        response = httpx.request(
            method, base + path, content=body, headers=headers, verify=_tls(), timeout=5
        )
    except httpx.HTTPError:
        return 0, {}
    try:
        data = response.json()
    except ValueError:
        data = {}
    return response.status_code, data if isinstance(data, dict) else {}


def _send(path: str, body: bytes, idempotency_key: str) -> tuple[int, dict]:
    return gateway_request("POST", path, body, idempotency_key)


def _get(path: str) -> tuple[int, dict]:
    return gateway_request("GET", path)


def apply_result(db: Session, result: JobStatus) -> bool:
    """Callback and reconciliation use this same atomic, idempotent state transition."""
    if result.status not in {"REGISTERED", "FAILED", "DEAD"}:
        raise HTTPException(422, "A terminal registration result is required")
    task = (
        db.query(IntegrationOutbox)
        .filter_by(idempotency_key=result.idempotency_key)
        .with_for_update()
        .first()
    )
    if task is None or task.operation != "REGISTER_DOCUMENT":
        raise HTTPException(404, "Integration job not found")
    req = task.request
    if req.status != RequestStatus.APPROVED or (
        req.gateway_job_id and req.gateway_job_id != result.gateway_job_id
    ):
        raise HTTPException(409, "Result does not match the approved request")
    if task.gateway_job_id and task.gateway_job_id != result.gateway_job_id:
        raise HTTPException(409, "Result does not match the accepted job")
    allowed: ColumnElement[bool] = Request.integration_status.in_(["PENDING", "SENT"])
    if result.status == "REGISTERED":
        allowed = or_(allowed, Request.integration_status == "DEAD")
    elif result.status == "DEAD":
        allowed = or_(
            allowed, (Request.integration_status == "DEAD") & Request.gateway_job_id.is_(None)
        )
    changed = db.execute(
        update(Request)
        .where(
            Request.id == req.id,
            Request.status == RequestStatus.APPROVED,
            allowed,
            or_(Request.gateway_job_id.is_(None), Request.gateway_job_id == result.gateway_job_id),
        )
        .values(
            integration_status=result.status,
            integration_mode=result.mode,
            gateway_job_id=result.gateway_job_id,
            external_sync_id=result.external_ref,
            integration_completed_at=result.occurred_at,
        ),
        execution_options={"synchronize_session": False},
    )
    applied = cast(CursorResult, changed).rowcount == 1
    db.refresh(req)
    if not applied:
        if (req.integration_status, req.gateway_job_id, req.external_sync_id) != (
            result.status,
            result.gateway_job_id,
            result.external_ref,
        ):
            raise HTTPException(409, "Conflicting terminal registration result")
        return False
    task.gateway_job_id = result.gateway_job_id
    task.status = "DONE" if result.status == "REGISTERED" else result.status
    task.last_error = result.error_code[:20] if result.error_code else None
    task.completed_at = result.occurred_at
    db.add(
        RequestEvent(
            request_id=req.id,
            actor_id=None,
            event_type=RequestEventType.COMMENTED,
            comment=f"MOCK Documentolog: {result.status}"
            + (f" ({result.external_ref})" if result.external_ref else ""),
        )
    )
    notification_service.create_notification(
        db,
        req.user_id,
        "MOCK document registered"
        if result.status == "REGISTERED"
        else "MOCK document registration failed",
        f"{req.request_code}: {result.status}. MOCK only; no official document or signature was created.",
        NotificationType.REQUEST,
        "request",
        req.request_code,
    )
    audit_service.log_event(
        db,
        action="INTEGRATION_" + result.status,
        target_type="request",
        target_id=req.request_code,
        details={"mode": "MOCK", "status": result.status},
    )
    return True


def _fail(db: Session, task: IntegrationOutbox, code: int, reason: str) -> None:
    now = datetime.now(timezone.utc)
    task.last_error = reason
    transient = code in (0, 429) or code >= 500
    if transient and task.attempts <= len(BACKOFF_SECONDS):
        task.next_attempt_at = now + timedelta(
            seconds=BACKOFF_SECONDS[task.attempts - 1] * random.uniform(0.8, 1.2)
        )
        return
    task.status = "DEAD" if transient else "FAILED"
    task.request.integration_status = task.status
    for hr in db.query(User).filter(User.role == UserRole.HR_ADMIN, User.is_active.is_(True)):
        db.add(
            Notification(
                user_id=hr.id,
                title="Integration delivery failed",
                message=f"{task.request.request_code}: {reason}. Review the integration queue.",
                type=NotificationType.SYSTEM,
                reference_type="request",
                reference_id=task.request.request_code,
            )
        )


def dispatch_one(db: Session, send: Send | None = None, get: Get | None = None) -> bool:
    if not settings.INTEGRATION_GATEWAY_URL:
        return False
    send, get = send or _send, get or _get
    now = datetime.now(timezone.utc)
    task = (
        db.query(IntegrationOutbox)
        .filter(
            IntegrationOutbox.status.in_(["PENDING", "SENT"]),
            IntegrationOutbox.next_attempt_at <= now,
        )
        .order_by(IntegrationOutbox.id)
        .with_for_update(skip_locked=True)
        .first()
    )
    if task is None:
        db.rollback()
        return False
    task.attempts += 1
    if task.operation != "REGISTER_DOCUMENT" or not task.payload:
        _fail(db, task, 422, "LEGACY_CONTRACT")
        db.commit()
        return True
    try:
        payload = DocumentRequest.model_validate(task.payload)
    except ValidationError:
        _fail(db, task, 422, "INVALID_CONTRACT")
        db.commit()
        return True
    # Recover a job after a lost response/restart by its stable key; POST itself is idempotent.
    if task.status == "SENT":
        code, data = get("/v1/documents/" + task.idempotency_key)
    else:
        code, data = send(
            "/v1/documents",
            payload.model_dump_json(exclude_none=True).encode(),
            task.idempotency_key,
        )
    try:
        result = JobStatus.model_validate(data) if 200 <= code < 300 else None
        if result and (
            result.idempotency_key != task.idempotency_key
            or (task.gateway_job_id and task.gateway_job_id != result.gateway_job_id)
        ):
            result = None
    except ValidationError:
        result = None
    if 200 <= code < 300 and result is None:
        _fail(db, task, 502, "INVALID_ACK")
    elif result:
        task.last_error = None
        task.attempts = 0
        task.gateway_job_id = result.gateway_job_id
        # A callback can win this race; never regress its terminal result to SENT.
        db.refresh(task.request)
        if result.status in {"REGISTERED", "FAILED", "DEAD"}:
            apply_result(db, result)
        else:
            task.status = "SENT"
            task.sent_at = task.sent_at or now
            task.next_attempt_at = now + timedelta(seconds=30)
            task.request.gateway_job_id = result.gateway_job_id
            task.request.integration_mode = result.mode
            if task.request.integration_status == "PENDING":
                task.request.integration_status = "SENT"
    elif code == 404 and task.status == "SENT":
        # Gateway storage unavailable/replaced: resubmit same immutable contract and key.
        task.status = "PENDING"
        _fail(db, task, 503, "JOB_NOT_FOUND")
    else:
        _fail(db, task, code, f"HTTP_{code}" if code else "NETWORK")
    audit_service.log_event(
        db,
        action="INTEGRATION_DELIVERY",
        target_type="request",
        target_id=task.request.request_code,
        details={"status": task.status, "attempt": task.attempts, "http_status": code},
    )
    db.commit()
    return True


def main() -> None:
    from app.database import SessionLocal, engine
    from app.integrations.profile_sync import sync_profiles
    from app.migrate import require_current_schema

    if not settings.INTEGRATION_GATEWAY_URL:
        raise SystemExit("INTEGRATION_GATEWAY_URL is empty; integrations are disabled")
    require_current_schema(engine)
    while True:
        with SessionLocal() as db:
            while dispatch_one(db):
                pass
        with SessionLocal() as db:
            sync_profiles(db)
        time.sleep(5)


if __name__ == "__main__":
    main()
