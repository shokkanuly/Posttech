from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.localization import LocalizedRoute
from app.models.academy import Enrollment
from app.models.enums import RequestStatus, UserRole
from app.models.profile import EmployeeProfile
from app.models.request import Request
from app.models.user import User
from app.schemas.auth import MeResponse, ProfileBrief, UserResponse
from app.schemas.profile import DashboardStatsResponse, EmployeeProfileResponse
from app.services.academy_service import academy_service
from app.services.auth_service import get_current_user
from app.services.notification_service import notification_service

router = APIRouter(route_class=LocalizedRoute, prefix="/me", tags=["Current User & Profile"])


@router.get("", response_model=MeResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == current_user.id).first()
    manager_name = profile.manager.full_name if (profile and profile.manager) else None

    profile_brief = None
    if profile:
        profile_brief = ProfileBrief(
            employee_code=profile.employee_code,
            company=profile.company,
            department=profile.department,
            position=profile.position,
            manager_name=manager_name,
            leave_balance_days=profile.leave_balance_days,
            location=profile.location,
        )

    return MeResponse(
        user=UserResponse.model_validate(current_user),
        profile=profile_brief,
    )


@router.get("/profile", response_model=EmployeeProfileResponse)
def get_my_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == current_user.id).first()
    manager_name = profile.manager.full_name if (profile and profile.manager) else None

    if not profile:
        raise HTTPException(404, "HR profile is not available")
    return EmployeeProfileResponse(
        id=profile.id if profile else 0,
        user_id=current_user.id,
        full_name=current_user.full_name,
        email=current_user.email,
        employee_code=profile.employee_code if profile else "N/A",
        company=profile.company if profile else "Jana Post Kazakhstan",
        department=profile.department if profile else "General",
        position=profile.position if profile else current_user.role.value.capitalize(),
        manager_id=profile.manager_id if profile else None,
        manager_name=manager_name,
        hire_date=profile.hire_date if profile else current_user.created_at.date(),
        leave_balance_days=profile.leave_balance_days if profile else 0.0,
        location=profile.location if profile else "Almaty, Kazakhstan",
        is_official_hr_data=False,
        learning_progress_percent=academy_service.get_user_overall_learning_progress(
            db, current_user.id
        ),
        courses=[c for c in academy_service.get_user_courses(db, current_user) if c.assigned],
        read_only=True,
    )


@router.get("/dashboard", response_model=DashboardStatsResponse)
def get_my_dashboard(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == current_user.id).first()

    # User's own pending requests
    open_requests = (
        db.query(Request)
        .filter(Request.user_id == current_user.id, Request.status == RequestStatus.PENDING)
        .count()
    )

    # Manager's pending team review count
    if current_user.role == UserRole.MANAGER:
        pending_attention = (
            db.query(Request)
            .join(EmployeeProfile, EmployeeProfile.user_id == Request.user_id)
            .filter(
                EmployeeProfile.manager_id == current_user.id,
                Request.status == RequestStatus.PENDING,
            )
            .count()
        )
    elif current_user.role == UserRole.HR_ADMIN:
        pending_attention = (
            db.query(Request).filter(Request.status == RequestStatus.PENDING).count()
        )
    else:
        pending_attention = open_requests

    # Real persisted learning progress
    overall_learning = academy_service.get_user_overall_learning_progress(db, current_user.id)
    assigned_courses = db.query(Enrollment).filter(Enrollment.user_id == current_user.id).count()
    unread_notifs = notification_service.get_unread_count(db, current_user.id)

    # Avatar initials
    parts = current_user.full_name.split()
    avatar = "".join([p[0].upper() for p in parts[:2]]) if parts else "JP"

    # Greeting
    first_name = parts[0] if parts else current_user.full_name
    greeting = f"Good afternoon, {first_name}"

    return DashboardStatsResponse(
        user_name=current_user.full_name,
        user_role=profile.position if profile else current_user.role.value.capitalize(),
        user_avatar=avatar,
        greeting=greeting,
        leave_balance_days=profile.leave_balance_days if profile else 0.0,
        open_requests_count=open_requests,
        pending_attention_count=pending_attention,
        learning_progress_percent=overall_learning,
        assigned_courses_count=assigned_courses,
        unread_notifications_count=unread_notifs,
    )
