from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field


def normalize_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


UTCDateTime = Annotated[datetime, AfterValidator(normalize_utc)]
DatabaseID = Annotated[int, Field(gt=0, le=2**63 - 1)]
BodyDatabaseID = Annotated[int, Field(gt=0, le=2**63 - 1, strict=True)]


class ErrorField(BaseModel):
    location: list[str | int]
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    fields: list[ErrorField] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    detail: str
    error: ErrorBody
    request_id: str


class MessageResponse(BaseModel):
    message: str


class ReadAllResponse(MessageResponse):
    count: int


class PublicConfig(BaseModel):
    demo_mode: bool
    demo_accounts: dict[str, str]


class TeamMemberResponse(BaseModel):
    user_id: int
    full_name: str
    employee_code: str
    department: str
    position: str
    leave_balance_days: float
    hire_date: str
    company: str = ""
    manager_name: str | None = None
    used_days: float = 0  # approved vacation days
    pending_days: float = 0  # days in pending vacation requests (reserved)
    available_days: float = 0  # balance minus reserved days
    learning_progress_percent: float = 0


class AuditResponse(BaseModel):
    id: int
    action: str
    actor_id: int | None
    actor_name: str
    target_type: str | None
    target_id: str | None
    details: str | None
    timestamp: UTCDateTime


class HealthResponse(BaseModel):
    status: str
    platform: str
    environment: str
    version: str


class NotificationCountResponse(BaseModel):
    unread: int


class AdminSummaryResponse(BaseModel):
    active_accounts: int
    pending_requests: int
    knowledge_chunks: int
