from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=256, repr=False)


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
    expires_in: int


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
