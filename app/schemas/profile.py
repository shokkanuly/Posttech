from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.academy import CourseResponse
from app.schemas.common import TeamMemberResponse, UTCDateTime
from app.schemas.request import RequestResponse


class EmployeeProfileResponse(BaseModel):
    id: int
    user_id: int
    full_name: str
    email: str
    employee_code: str
    company: str
    department: str
    position: str
    manager_id: Optional[int] = None
    manager_name: Optional[str] = None
    hire_date: date
    leave_balance_days: float
    location: str
    phone: Optional[str] = None
    emergency_contact: Optional[str] = None
    # Changes awaiting manager/HR approval: {field: {"from": old, "to": new}}.
    pending_profile_change: Optional[dict[str, dict[str, Optional[str]]]] = None
    data_source: str = "Local HR records; 1C is unconnected"
    source_mode: str = "LOCAL"
    synced_at: Optional[UTCDateTime] = None
    as_of: Optional[UTCDateTime] = None
    is_stale: bool = False
    learning_progress_percent: float = 0
    courses: list[CourseResponse] = Field(default_factory=list)
    is_official_hr_data: bool = False
    read_only: bool = True

    model_config = ConfigDict(from_attributes=True)


class DashboardStatsResponse(BaseModel):
    user_name: str
    user_role: str
    user_avatar: str
    greeting: str
    leave_balance_days: float
    open_requests_count: int
    pending_attention_count: int
    learning_progress_percent: float
    assigned_courses_count: int
    unread_notifications_count: int


class HistoryItem(BaseModel):
    """One dated fact in an employee's history: a request decision or a learning step."""

    at: UTCDateTime
    kind: Literal["request", "learning"]
    event: str  # SUBMITTED / APPROVED / REJECTED / LESSON_PASSED / COURSE_COMPLETED
    reference: str  # request code or course title
    detail: Optional[str] = None  # comment or lesson title
    actor: Optional[str] = None


class EmployeeDetailResponse(TeamMemberResponse):
    """A team member's HR card for their manager or HR: profile, leave, requests, learning."""

    location: str
    phone: Optional[str] = None
    # Current account/emergency-contact projection is HR only. Assigned reviewers
    # can see submitted contact changes in requests, including emergency contact.
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    account_created_at: Optional[UTCDateTime] = None
    last_sign_in_at: Optional[UTCDateTime] = None
    emergency_contact: Optional[str] = None
    requests: list[RequestResponse] = Field(default_factory=list)
    courses: list[CourseResponse] = Field(default_factory=list)
    history: list[HistoryItem] = Field(default_factory=list)
