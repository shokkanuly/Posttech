from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # e.g., "USER_LOGIN", "REQUEST_SUBMITTED", "REQUEST_APPROVED"
    target_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # e.g., "request", "profile", "course"
    target_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    actor: Mapped[User | None] = relationship("User", back_populates="audit_events")


if TYPE_CHECKING:
    from app.models.user import User
