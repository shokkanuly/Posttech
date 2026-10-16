from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr
from app.models.enums import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ProfileBrief(BaseModel):
    employee_code: str
    company: str
    department: str
    position: str
    manager_name: Optional[str] = None
    leave_balance_days: float
    location: str


class MeResponse(BaseModel):
    user: UserResponse
    profile: Optional[ProfileBrief] = None
