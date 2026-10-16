from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole), nullable=False, default=UserRole.EMPLOYEE
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    profile: Mapped[EmployeeProfile | None] = relationship(
        "EmployeeProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        foreign_keys="EmployeeProfile.user_id",
    )
    requests: Mapped[list[Request]] = relationship(
        "Request", back_populates="user", foreign_keys="Request.user_id"
    )
    reviewed_requests: Mapped[list[Request]] = relationship(
        "Request", back_populates="reviewer", foreign_keys="Request.reviewer_id"
    )
    enrollments: Mapped[list[Enrollment]] = relationship(
        "Enrollment", back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[list[Notification]] = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        "AuditEvent", back_populates="actor", foreign_keys="AuditEvent.actor_id"
    )


if TYPE_CHECKING:
    from app.models.academy import Enrollment
    from app.models.audit import AuditEvent
    from app.models.notification import Notification
    from app.models.profile import EmployeeProfile
    from app.models.request import Request
