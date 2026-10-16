from datetime import date
from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    employee_code = Column(String(50), unique=True, index=True, nullable=False)  # e.g., "JP-10428"
    company = Column(String(255), default="Jana Post Kazakhstan", nullable=False)
    department = Column(String(255), nullable=False)
    position = Column(String(255), nullable=False)
    manager_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    hire_date = Column(Date, nullable=False)
    leave_balance_days = Column(Float, default=24.0, nullable=False)
    location = Column(String(255), default="Almaty, Kazakhstan", nullable=False)

    # Relationships
    user = relationship("User", back_populates="profile", foreign_keys=[user_id])
    manager = relationship("User", foreign_keys=[manager_id])
