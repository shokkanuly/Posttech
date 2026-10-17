"""Transactional outbox to the integration gateway (docs/INTEGRATIONS.md, section 4).

Tasks are written in the approval transaction. The worker delivers each with a signed
request, retries transient failures with backoff and parks the rest as DEAD for HR.
Run: python -m app.integrations.outbox
"""

import json
import random
import ssl
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import cast
from urllib.parse import urlsplit

import httpx
from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.config import settings
from app.integrations import signing
from app.models.enums import NotificationType, RequestEventType, UserRole
from app.models.integration import IntegrationOutbox
from app.models.request import Request, RequestEvent
from app.models.user import User
from app.services.audit_service import audit_service
from app.services.notification_service import notification_service

Send = Callable[[str, bytes, str], tuple[int, dict]]

# operation -> (gateway path, idempotency suffix, progress on success, follow-up operation)
OPERATIONS: dict[str, tuple[str, str, str, str | None]] = {
    "ONE_C_ORDER": ("/v1/1c/orders", "1c-order", "ORDER_CREATED", "DOCUMENTOLOG_REGISTER"),
    "DOCUMENTOLOG_REGISTER": ("/v1/documentolog/documents", "doclog", "SIGNING", None),
}
# Progress only moves forward, so repeated or out-of-order reports change nothing.
RANK = {"QUEUED": 0, "ORDER_CREATED": 1, "SIGNING": 2, "SIGNED": 3, "SIGN_REJECTED": 3}
EVENT_TEXT = {
    "ORDER_CREATED": "1C:ZUP created the order",
    "SIGNING": "Order sent to Documentolog for signing",
    "SIGNED": "Order signed in Documentolog",
    "SIGN_REJECTED": "Order was rejected in Documentolog; HR will follow up",
}
BACKOFF_SECONDS = (30, 60, 300, 900, 3600, 21600, 43200)  # 8 attempts over about a day


def enqueue(db: Session, req: Request, operation: str) -> None:
    """Add a delivery task to the caller's transaction."""
    db.add(
        IntegrationOutbox(
            request_id=req.id,
            operation=operation,
            idempotency_key=f"{req.request_code}:{OPERATIONS[operation][1]}",
            status="PENDING",
            attempts=0,
            next_attempt_at=datetime.now(timezone.utc),
        )
    )


def advance(db: Session, req: Request, status: str) -> bool:
    """Move integration progress forward and record it in the request history."""
    lower = [name for name, rank in RANK.items() if rank < RANK[status]]
    result = db.execute(
        update(Request)
        .where(Request.id == req.id, Request.integration_status.in_(lower))
        .values(integration_status=status),
        execution_options={"synchronize_session": False},
    )
    if cast(CursorResult, result).rowcount != 1:
        return False
    db.add(
        RequestEvent(
            request_id=req.id,
            actor_id=None,
            event_type=RequestEventType.COMMENTED,
            comment=EVENT_TEXT[status],
        )
    )
    return True


def _payload(operation: str, req: Request) -> bytes:
    # Only the fields listed in docs/INTEGRATIONS.md; no reason text, salary or contacts.
    if operation == "ONE_C_ORDER":
        # A missing code is a data error: the gateway answers 4xx and the task goes to DEAD.
        employee = req.user.profile
        approver = req.reviewer.profile if req.reviewer else None
        data = {
            "request_code": req.request_code,
            "employee_code": employee.employee_code if employee else None,
            "type": req.type.name,
            "start_date": req.start_date.isoformat(),
            "end_date": (req.end_date or req.start_date).isoformat(),
            "amount": req.amount,
            "approver_employee_code": approver.employee_code if approver else None,
        }
    else:
        data = {"request_code": req.request_code, "one_c_document_id": req.external_sync_id}
    return json.dumps(data, separators=(",", ":")).encode()


@lru_cache(maxsize=1)
def _tls() -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=settings.INTEGRATION_TLS_CA or None)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    if settings.INTEGRATION_TLS_CERT:
        context.load_cert_chain(settings.INTEGRATION_TLS_CERT, settings.INTEGRATION_TLS_KEY or None)
    return context


def _send(path: str, body: bytes, idempotency_key: str) -> tuple[int, dict]:
    """POST a signed body; status 0 means the gateway was unreachable."""
    base = settings.INTEGRATION_GATEWAY_URL.rstrip("/")
    headers = signing.sign(
        settings.INTEGRATION_OUTBOUND_KEY_ID,
        settings.INTEGRATION_OUTBOUND_KEY,
        "POST",
        urlsplit(base).path + path,
        body,
    )
    headers |= {"Content-Type": "application/json", "Idempotency-Key": idempotency_key}
    try:
        response = httpx.post(base + path, content=body, headers=headers, verify=_tls(), timeout=10)
    except httpx.HTTPError:
        return 0, {}
    try:
        data = response.json()
    except ValueError:
        data = {}
    return response.status_code, data if isinstance(data, dict) else {}


def dispatch_one(db: Session, send: Send = _send) -> bool:
    """Deliver one due task in its own transaction; False when nothing is due."""
    now = datetime.now(timezone.utc)
    task = (
        db.query(IntegrationOutbox)
        .filter(IntegrationOutbox.status == "PENDING", IntegrationOutbox.next_attempt_at <= now)
        .order_by(IntegrationOutbox.id)
        .with_for_update(skip_locked=True)
        .first()
    )
    if task is None:
        db.rollback()
        return False
    req = task.request
    path, _, progress, follow_up = OPERATIONS[task.operation]
    code, data = send(path, _payload(task.operation, req), task.idempotency_key)
    task.attempts += 1
    task.last_error = None if 200 <= code < 300 else (f"HTTP_{code}" if code else "NETWORK")
    if 200 <= code < 300:
        task.status = "DONE"
        if task.operation == "ONE_C_ORDER" and data.get("external_id"):
            req.external_sync_id = str(data["external_id"])[:100]
        advance(db, req, progress)
        if follow_up:
            enqueue(db, req, follow_up)
    elif (code in (0, 429) or code >= 500) and task.attempts <= len(BACKOFF_SECONDS):
        delay = BACKOFF_SECONDS[task.attempts - 1] * random.uniform(0.8, 1.2)
        task.next_attempt_at = now + timedelta(seconds=delay)
    else:
        task.status = "DEAD"
        for hr in db.query(User).filter(User.role == UserRole.HR_ADMIN, User.is_active.is_(True)):
            notification_service.create_notification(
                db=db,
                user_id=hr.id,
                title="Integration delivery failed",
                message=f"Request {req.request_code} could not be delivered to the integration gateway. Check the integration queue.",
                type=NotificationType.SYSTEM,
                reference_type="request",
                reference_id=req.request_code,
            )
    audit_service.log_event(
        db=db,
        action="INTEGRATION_" + ("RETRY" if task.status == "PENDING" else task.status),
        target_type="request",
        target_id=req.request_code,
        details={"operation": task.operation, "attempt": task.attempts, "http_status": code},
    )
    db.commit()
    return True


def main() -> None:
    from app.database import SessionLocal, engine
    from app.migrate import require_current_schema

    if not settings.INTEGRATION_GATEWAY_URL:
        raise SystemExit("INTEGRATION_GATEWAY_URL is not configured; nothing to deliver")
    require_current_schema(engine)
    while True:
        with SessionLocal() as db:
            while dispatch_one(db):
                pass
        time.sleep(5)


if __name__ == "__main__":
    main()
