from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    employee_code: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )  # e.g., "JP-10428"
    company: Mapped[str] = mapped_column(
        String(255), default="Jana Post Kazakhstan", nullable=False
    )
    department: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[str] = mapped_column(String(255), nullable=False)
    manager_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    leave_balance_days: Mapped[float] = mapped_column(Float, default=24.0, nullable=False)
    location: Mapped[str] = mapped_column(String(255), default="Almaty, Kazakhstan", nullable=False)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="profile", foreign_keys=[user_id])
    manager: Mapped[User | None] = relationship("User", foreign_keys=[manager_id])


if TYPE_CHECKING:
    from app.models.user import User
