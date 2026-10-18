from datetime import date
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import RequestEventType, RequestStatus, RequestType
from app.schemas.common import UTCDateTime


class ProfileChanges(BaseModel):
    """Contact details an employee may change; HR-owned fields are not accepted."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    phone: Optional[str] = Field(default=None, pattern=r"^\+?[0-9][0-9 ()\-]{5,30}$")
    location: Optional[str] = Field(default=None, min_length=2, max_length=255)
    emergency_contact: Optional[str] = Field(default=None, min_length=2, max_length=255)


class RequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    type: RequestType
    start_date: Optional[date] = None  # required except for a profile update (dated today)
    end_date: Optional[date] = None
    amount: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    reason: Optional[str] = Field(default=None, max_length=2000)
    profile_changes: Optional[ProfileChanges] = None

    @model_validator(mode="after")
    def validate_request(self):
        if self.type == RequestType.PROFILE_UPDATE:
            if self.start_date or self.end_date or self.amount is not None:
                raise ValueError("Profile updates cannot specify dates or an amount")
            if not self.profile_changes or not self.profile_changes.model_dump(exclude_none=True):
                raise ValueError("Profile updates must change at least one field")
            return self
        if self.profile_changes is not None:
            raise ValueError("Only profile updates can change profile fields")
        if self.start_date is None:
            raise ValueError("Start date is required")
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("End date cannot be earlier than start date")
        if self.type == RequestType.ADVANCE_PAYMENT and self.amount is None:
            raise ValueError("Advance payment amount must be greater than zero")
        if self.type == RequestType.VACATION and self.amount is not None:
            raise ValueError("Vacation requests cannot specify an advance amount")
        if self.type == RequestType.ADVANCE_PAYMENT and self.end_date is not None:
            raise ValueError("Advance requests cannot specify a vacation end date")
        return self


class RequestReview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    action: Optional[Literal["approve", "reject"]] = None
    comment: Optional[str] = Field(default=None, max_length=2000)


class RequestEventResponse(BaseModel):
    id: int
    actor_id: Optional[int] = None
    actor_name: str
    event_type: RequestEventType
    comment: Optional[str] = None
    created_at: UTCDateTime

    model_config = ConfigDict(from_attributes=True)


class RequestResponse(BaseModel):
    id: int
    request_code: str
    user_id: int
    user_name: str
    department: str
    type: RequestType
    start_date: date
    end_date: Optional[date] = None
    amount: Optional[float] = None
    reason: Optional[str] = None
    status: RequestStatus
    reviewer_id: Optional[int] = None
    reviewer_name: Optional[str] = None
    review_comment: Optional[str] = None
    external_sync_id: Optional[str] = None
    external_ref: Optional[str] = None
    sync_status: str = "NOT_REQUIRED"
    integration_mode: Optional[str] = None
    submitted_date_formatted: str
    period_or_details: str
    vacation_days: Optional[float] = None  # chargeable days under the configured local calendar
    weekend_days: Optional[int] = None  # inside the vacation and charged
    holiday_days: Optional[int] = None  # public holidays inside the vacation, not charged
    profile_changes: Optional[dict[str, dict[str, Optional[str]]]] = None
    created_at: UTCDateTime
    updated_at: UTCDateTime

    model_config = ConfigDict(from_attributes=True)


class LeaveDay(BaseModel):
    day: date
    kind: Literal["workday", "weekend", "holiday"]
    holiday: Optional[str] = None


class LeaveCalendarResponse(BaseModel):
    """Every day of a planned vacation, marked, with what will be charged."""

    days: List[LeaveDay]
    calendar_days: int
    weekend_days: int
    holiday_days: int
    charged_days: float
    available_days: float


class RequestDetailResponse(RequestResponse):
    events: List[RequestEventResponse] = []
    leave_days: List[LeaveDay] = []
