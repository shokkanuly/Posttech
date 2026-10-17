from datetime import datetime
from typing import List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.localization import LocalizedRoute
from app.models.academy import Enrollment, LessonProgress
from app.models.enums import RequestStatus, UserRole
from app.models.profile import EmployeeProfile
from app.models.request import Request, RequestEvent
from app.models.user import User
from app.pagination import Page
from app.schemas.common import DatabaseID, TeamMemberResponse
from app.schemas.profile import EmployeeDetailResponse
from app.schemas.request import RequestResponse
from app.services.academy_service import academy_service
from app.services.auth_service import require_role
from app.services.request_service import request_service

router = APIRouter(route_class=LocalizedRoute, prefix="/manager", tags=["Manager Portal"])
reviewer = require_role(UserRole.MANAGER, UserRole.HR_ADMIN)


@router.get("/requests", response_model=List[RequestResponse])
def get_manager_team_requests(
    page: Page,
    status: Optional[RequestStatus] = Query(None, description="Filter by status (e.g., Pending)"),
    current_user: User = Depends(reviewer),
    db: Session = Depends(get_db),
):
    team_requests = request_service.get_team_requests(
        db, current_user, status_filter=status, limit=page.limit, offset=page.offset
    )
    return [request_service.to_response(r) for r in team_requests]


def scoped_profiles(db: Session, current_user: User):
    """Managers see their direct reports; HR sees every profile. Enforced here, not in the UI."""
    query = (
        db.query(EmployeeProfile)
        .join(User, User.id == EmployeeProfile.user_id)
        .options(joinedload(EmployeeProfile.user), joinedload(EmployeeProfile.manager))
    )
    if current_user.role != UserRole.HR_ADMIN:
        query = query.filter(EmployeeProfile.manager_id == current_user.id)
    return query.filter(User.is_active.is_(True))


def learning_progress(db: Session, user_ids: list[int]) -> dict[int, float]:
    """Average enrollment progress per user in one grouped query."""
    rows = (
        db.query(Enrollment.user_id, func.avg(Enrollment.progress_percent))
        .filter(Enrollment.user_id.in_(user_ids))
        .group_by(Enrollment.user_id)
        .all()
    )
    return {user_id: round(float(avg or 0.0), 1) for user_id, avg in rows}


def member_card(
    profile: EmployeeProfile, leave: dict[str, float], progress: dict[int, float]
) -> dict:
    return {
        "user_id": profile.user_id,
        "full_name": profile.user.full_name,
        "employee_code": profile.employee_code,
        "company": profile.company,
        "department": profile.department,
        "position": profile.position,
        "manager_name": profile.manager.full_name if profile.manager else None,
        "hire_date": str(profile.hire_date),
        "leave_balance_days": profile.leave_balance_days,
        "used_days": leave["used_days"],
        "pending_days": leave["pending_days"],
        "available_days": max(0.0, profile.leave_balance_days - leave["pending_days"]),
        "learning_progress_percent": progress.get(profile.user_id, 0.0),
    }


def employee_history(db: Session, user_id: int) -> list[dict]:
    """Request decisions (who, when, comment) and learning steps, newest first."""
    events = (
        db.query(RequestEvent)
        .join(Request, Request.id == RequestEvent.request_id)
        .options(joinedload(RequestEvent.actor), joinedload(RequestEvent.request))
        .filter(Request.user_id == user_id)
        .order_by(RequestEvent.created_at.desc(), RequestEvent.id.desc())
        .limit(300)
        .all()
    )
    history = [
        {
            "at": e.created_at,
            "kind": "request",
            "event": e.event_type.value,
            "reference": e.request.request_code,
            "detail": e.comment,
            "actor": e.actor.full_name if e.actor else "System",
        }
        for e in events
    ]
    lessons = (
        db.query(LessonProgress)
        .join(Enrollment, Enrollment.id == LessonProgress.enrollment_id)
        .options(
            joinedload(LessonProgress.lesson),
            joinedload(LessonProgress.enrollment).joinedload(Enrollment.course),
        )
        .filter(Enrollment.user_id == user_id, LessonProgress.completed_at.is_not(None))
        .order_by(LessonProgress.completed_at.desc(), LessonProgress.id.desc())
        .limit(300)
        .all()
    )
    history += [
        {
            "at": p.completed_at,
            "kind": "learning",
            "event": "LESSON_PASSED" if p.quiz_passed else "LESSON_COMPLETED",
            "reference": p.enrollment.course.title,
            "detail": p.lesson.title,
        }
        for p in lessons
    ]
    finished = (
        db.query(Enrollment)
        .options(joinedload(Enrollment.course))
        .filter(Enrollment.user_id == user_id, Enrollment.completed_at.is_not(None))
        .order_by(Enrollment.completed_at.desc(), Enrollment.id.desc())
        .limit(300)
        .all()
    )
    history += [
        {
            "at": e.completed_at,
            "kind": "learning",
            "event": "COURSE_COMPLETED",
            "reference": e.course.title,
            "detail": f"{round(e.score or 0)}%",
        }
        for e in finished
    ]
    return sorted(history, key=lambda item: cast(datetime, item["at"]), reverse=True)[:300]


@router.get("/team", response_model=list[TeamMemberResponse])
def get_manager_team_members(
    page: Page, current_user: User = Depends(reviewer), db: Session = Depends(get_db)
):
    profiles = (
        scoped_profiles(db, current_user)
        .order_by(EmployeeProfile.id)
        .offset(page.offset)
        .limit(page.limit)
        .all()
    )
    ids = [p.user_id for p in profiles]
    leave = request_service.leave_summary(db, ids)
    progress = learning_progress(db, ids)
    return [member_card(p, leave[p.user_id], progress) for p in profiles]


@router.get("/team/{user_id}", response_model=EmployeeDetailResponse)
def get_team_member(
    user_id: DatabaseID, current_user: User = Depends(reviewer), db: Session = Depends(get_db)
):
    profile = scoped_profiles(db, current_user).filter(EmployeeProfile.user_id == user_id).first()
    if not profile:
        # Same answer for "missing" and "not in your team": scope does not leak existence.
        raise HTTPException(404, "Employee not found in your scope")
    requests = (
        db.query(Request)
        .options(joinedload(Request.user).joinedload(User.profile), joinedload(Request.reviewer))
        .filter(Request.user_id == user_id)
        .order_by(Request.created_at.desc(), Request.id.desc())
        .limit(100)
        .all()
    )
    return {
        **member_card(
            profile,
            request_service.leave_summary(db, [user_id])[user_id],
            learning_progress(db, [user_id]),
        ),
        "location": profile.location,
        "requests": [request_service.to_response(r) for r in requests],
        "courses": [c for c in academy_service.get_user_courses(db, profile.user) if c.assigned],
        "history": employee_history(db, user_id),
    }
