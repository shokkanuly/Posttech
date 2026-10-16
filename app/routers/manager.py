from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import RequestStatus, UserRole
from app.models.profile import EmployeeProfile
from app.models.user import User
from app.pagination import Page
from app.schemas.common import TeamMemberResponse
from app.schemas.request import RequestResponse
from app.services.auth_service import require_role
from app.services.request_service import request_service

router = APIRouter(prefix="/manager", tags=["Manager Portal"])


@router.get("/requests", response_model=List[RequestResponse])
def get_manager_team_requests(
    page: Page,
    status: Optional[RequestStatus] = Query(None, description="Filter by status (e.g., Pending)"),
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.HR_ADMIN)),
    db: Session = Depends(get_db),
):
    team_requests = request_service.get_team_requests(
        db, current_user, status_filter=status, limit=page.limit, offset=page.offset
    )
    return [request_service.to_response(r) for r in team_requests]


@router.get("/team", response_model=list[TeamMemberResponse])
def get_manager_team_members(
    page: Page,
    current_user: User = Depends(require_role(UserRole.MANAGER, UserRole.HR_ADMIN)),
    db: Session = Depends(get_db),
):
    query = db.query(EmployeeProfile)
    if current_user.role != UserRole.HR_ADMIN:
        query = query.filter(EmployeeProfile.manager_id == current_user.id)
    profiles = query.order_by(EmployeeProfile.id).offset(page.offset).limit(page.limit).all()
    return [
        {
            "user_id": p.user_id,
            "full_name": p.user.full_name,
            "employee_code": p.employee_code,
            "department": p.department,
            "position": p.position,
            "leave_balance_days": p.leave_balance_days,
            "hire_date": str(p.hire_date),
        }
        for p in profiles
    ]
