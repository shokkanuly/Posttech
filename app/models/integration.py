from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class IntegrationOutbox(Base):
    """Delivery task written in the same transaction as the approval it belongs to."""

    __tablename__ = "integration_outbox"
    __table_args__ = (Index("ix_integration_outbox_due", "status", "next_attempt_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="PENDING", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(20), nullable=True)  # code, no payload
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    request: Mapped[Request] = relationship("Request")


class IntegrationNonce(Base):
    """Nonces seen from the gateway; the primary key rejects a replayed request."""

    __tablename__ = "integration_nonces"

    nonce: Mapped[str] = mapped_column(String(64), primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)


if TYPE_CHECKING:
    from app.models.request import Request
