from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GatewayBase(DeclarativeBase):
    pass


class GatewayNonce(GatewayBase):
    __tablename__ = "gateway_nonces"
    nonce: Mapped[str] = mapped_column(String(64), primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


class GatewayJob(GatewayBase):
    __tablename__ = "gateway_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    body_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="PENDING", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    lease_token: Mapped[str | None] = mapped_column(String(32))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime)
    external_ref: Mapped[str | None] = mapped_column(String(100))
    error_code: Mapped[str | None] = mapped_column(String(40))
    recovery_key: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    callback_status: Mapped[str] = mapped_column(String(12), default="WAITING", index=True)
    callback_attempts: Mapped[int] = mapped_column(Integer, default=0)
    callback_next_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    callback_lease_until: Mapped[datetime | None] = mapped_column(DateTime)
    callback_lease_token: Mapped[str | None] = mapped_column(String(32))


class MockDocument(GatewayBase):
    __tablename__ = "mock_documents"
    idempotency_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    external_ref: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
