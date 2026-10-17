from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    true,
)
from sqlalchemy import Date as SQLDate
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import RequestEventType, RequestStatus, RequestType


class Request(Base):
    __tablename__ = "requests"
    __table_args__ = (UniqueConstraint("user_id", "submission_key", name="uq_request_submission"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    request_code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )  # e.g., "REQ-1042"
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[RequestType] = mapped_column(SQLEnum(RequestType), nullable=False)
    start_date: Mapped[date] = mapped_column(SQLDate, nullable=False)
    end_date: Mapped[date | None] = mapped_column(SQLDate, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )  # For advance payments (e.g., KZT)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submission_key: Mapped[str | None] = mapped_column(String(80))
    submission_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[RequestStatus] = mapped_column(
        SQLEnum(RequestStatus), default=RequestStatus.PENDING, nullable=False, index=True
    )
    reviewer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_sync_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # Reference to Documentolog/1C
    # Separate from employee-facing approval: PENDING/SENT/REGISTERED/FAILED/DEAD.
    integration_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    integration_mode: Mapped[str | None] = mapped_column(String(20))
    gateway_job_id: Mapped[str | None] = mapped_column(String(36))
    integration_completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    charged_leave_days: Mapped[float | None] = mapped_column(Float)
    leave_balance_confirmed: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="requests", foreign_keys=[user_id])
    reviewer: Mapped[User | None] = relationship(
        "User", back_populates="reviewed_requests", foreign_keys=[reviewer_id]
    )
    events: Mapped[list[RequestEvent]] = relationship(
        "RequestEvent",
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="RequestEvent.created_at.desc()",
    )


class RequestEvent(Base):
    __tablename__ = "request_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    request_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[RequestEventType] = mapped_column(SQLEnum(RequestEventType), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    request: Mapped[Request] = relationship("Request", back_populates="events")
    actor: Mapped[User | None] = relationship("User")


if TYPE_CHECKING:
    from app.models.user import User
