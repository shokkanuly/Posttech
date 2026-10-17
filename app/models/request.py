from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Date as SQLDate
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import RequestEventType, RequestStatus, RequestType


class Request(Base):
    __tablename__ = "requests"

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
    amount: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # For advance payments (e.g., KZT)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    # Forward-only gateway progress: QUEUED, ORDER_CREATED, SIGNING, SIGNED or SIGN_REJECTED.
    integration_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
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
