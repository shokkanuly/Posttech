"""Signed machine-only registration results, using the existing callback URL/headers."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Request as HTTPRequest
from pydantic import ValidationError
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.integrations import outbox, signing
from app.integrations.contracts import RegistrationResult
from app.models.integration import IntegrationNonce

router = APIRouter(prefix="/internal/integrations", include_in_schema=False)


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
    db.execute(
        delete(IntegrationNonce).where(IntegrationNonce.seen_at < now - timedelta(seconds=900))
    )
    db.add(IntegrationNonce(nonce=nonce, seen_at=now))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(401, "Invalid integration signature") from None


@router.post("/documentolog/status")
def documentolog_status(
    signed: tuple[bytes, str] = Depends(signed_request), db: Session = Depends(get_db)
):
    if not settings.INTEGRATION_GATEWAY_URL:
        raise HTTPException(503, "Integration gateway is disabled")
    body, nonce = signed
    remember_nonce(db, nonce)
    # Persist the anti-replay check even when the canonical body is invalid.
    db.commit()
    try:
        payload = RegistrationResult.model_validate_json(body)
    except ValidationError:
        raise HTTPException(422, "Invalid canonical result") from None
    if payload.nonce != nonce:
        raise HTTPException(401, "Invalid integration signature")
    applied = outbox.apply_result(db, payload)
    db.commit()
    return {"applied": applied}
