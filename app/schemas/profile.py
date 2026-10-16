from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict


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
    is_official_hr_data: bool = True
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
