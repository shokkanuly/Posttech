"""Signed callbacks from the integration gateway (docs/INTEGRATIONS.md).

Machine-to-machine only: no bearer token and hidden from the browser OpenAPI. Every call
needs a valid HMAC signature from INTEGRATION_INBOUND_KEYS and a nonce never seen before.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Request as HTTPRequest
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.integrations import outbox, signing
from app.models.enums import NotificationType
from app.models.integration import IntegrationNonce
from app.models.request import Request
from app.services.audit_service import audit_service
from app.services.notification_service import notification_service

router = APIRouter(prefix="/internal/integrations", include_in_schema=False)


class DocumentologStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_code: str = Field(max_length=50)
    status: Literal["SIGNED", "SIGN_REJECTED"]


async def signed_request(request: HTTPRequest) -> tuple[bytes, str]:
    body = await request.body()
    path = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    try:
        nonce = signing.verify(
            request.headers, settings.INTEGRATION_INBOUND_KEYS, request.method, path, body
        )
    except signing.SignatureError:
        raise HTTPException(401, "Invalid integration signature") from None
    return body, nonce


def remember_nonce(db: Session, nonce: str) -> None:
    now = datetime.now(timezone.utc)
    # Older nonces fail the timestamp check anyway, so they no longer need storing.
    db.execute(
        delete(IntegrationNonce).where(
            IntegrationNonce.seen_at < now - timedelta(seconds=3 * signing.MAX_SKEW_SECONDS)
        )
    )
    db.add(IntegrationNonce(nonce=nonce, seen_at=now))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(401, "Invalid integration signature") from None


@router.post("/documentolog/status")
def documentolog_status(
    request: HTTPRequest,
    signed: tuple[bytes, str] = Depends(signed_request),
    db: Session = Depends(get_db),
):
    body, nonce = signed
    remember_nonce(db, nonce)
    try:
        payload = DocumentologStatus.model_validate_json(body)
    except ValidationError:
        raise HTTPException(422, "Invalid input") from None
    req = db.query(Request).filter(Request.request_code == payload.request_code).first()
    if req is None:
        raise HTTPException(404, "Request not found")
    applied = outbox.advance(db, req, payload.status)
    if applied:
        notification_service.create_notification(
            db=db,
            user_id=req.user_id,
            title="Order signed" if payload.status == "SIGNED" else "Order rejected",
            message=outbox.EVENT_TEXT[payload.status],
            type=NotificationType.REQUEST,
            reference_type="request",
            reference_id=req.request_code,
        )
    audit_service.log_event(
        db=db,
        action="INTEGRATION_STATUS",
        target_type="request",
        target_id=req.request_code,
        details={
            "status": payload.status,
            "applied": applied,
            "key_id": request.headers["x-key-id"],
        },
    )
    db.commit()
    return {"applied": applied}
