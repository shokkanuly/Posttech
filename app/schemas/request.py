from datetime import date
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import RequestEventType, RequestStatus, RequestType
from app.schemas.common import UTCDateTime


class RequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    type: RequestType
    start_date: date
    end_date: Optional[date] = None
    amount: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    reason: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_request(self):
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
    submitted_date_formatted: str
    period_or_details: str
    created_at: UTCDateTime
    updated_at: UTCDateTime

    model_config = ConfigDict(from_attributes=True)


class RequestDetailResponse(RequestResponse):
    events: List[RequestEventResponse] = []
