from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, field_validator
from app.models.enums import RequestType, RequestStatus, RequestEventType


class RequestCreate(BaseModel):
    type: RequestType
    start_date: date
    end_date: Optional[date] = None
    amount: Optional[float] = None
    reason: Optional[str] = None

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, end_date, info):
        start_date = info.data.get("start_date")
        if start_date and end_date and end_date < start_date:
            raise ValueError("End date cannot be earlier than start date")
        return end_date

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, amount, info):
        req_type = info.data.get("type")
        if req_type == RequestType.ADVANCE_PAYMENT and (amount is None or amount <= 0):
            raise ValueError("Advance payment amount must be greater than zero")
        return amount


class RequestReview(BaseModel):
    action: str  # "approve" or "reject"
    comment: Optional[str] = None

    @field_validator("action")
    @classmethod
    def validate_action(cls, v):
        if v.lower() not in ["approve", "reject"]:
            raise ValueError("Action must be either 'approve' or 'reject'")
        return v.lower()


class RequestEventResponse(BaseModel):
    id: int
    actor_id: Optional[int] = None
    actor_name: str
    event_type: RequestEventType
    comment: Optional[str] = None
    created_at: datetime

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
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RequestDetailResponse(RequestResponse):
    events: List[RequestEventResponse] = []
