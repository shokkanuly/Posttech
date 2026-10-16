from datetime import datetime, date, timezone
from sqlalchemy import Column, Integer, String, Float, Date as SQLDate, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.enums import RequestType, RequestStatus, RequestEventType


class Request(Base):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True, index=True)
    request_code = Column(String(50), unique=True, index=True, nullable=False)  # e.g., "REQ-1042"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(SQLEnum(RequestType), nullable=False)
    start_date = Column(SQLDate, nullable=False)
    end_date = Column(SQLDate, nullable=True)
    amount = Column(Float, nullable=True)  # For advance payments (e.g., KZT)
    reason = Column(Text, nullable=True)
    status = Column(SQLEnum(RequestStatus), default=RequestStatus.PENDING, nullable=False, index=True)
    reviewer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    review_comment = Column(Text, nullable=True)
    external_sync_id = Column(String(100), nullable=True)  # Reference to Documentolog/1C
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="requests", foreign_keys=[user_id])
    reviewer = relationship("User", back_populates="reviewed_requests", foreign_keys=[reviewer_id])
    events = relationship("RequestEvent", back_populates="request", cascade="all, delete-orphan", order_by="RequestEvent.created_at.desc()")


class RequestEvent(Base):
    __tablename__ = "request_events"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("requests.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(SQLEnum(RequestEventType), nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    request = relationship("Request", back_populates="events")
    actor = relationship("User")
