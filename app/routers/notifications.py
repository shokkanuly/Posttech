from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.localization import LocalizedRoute
from app.models.academy import Course
from app.models.notification import Notification
from app.models.request import Request
from app.models.user import User
from app.pagination import Page
from app.schemas.common import DatabaseID, NotificationCountResponse, ReadAllResponse
from app.schemas.notification import NotificationResponse, NotificationUpdate
from app.services.auth_service import get_current_user
from app.services.notification_service import notification_service

router = APIRouter(route_class=LocalizedRoute, prefix="/notifications", tags=["Notifications"])


def to_responses(db: Session, notifs: list[Notification]) -> list[NotificationResponse]:
    """Resolve request/course codes to record ids in one query per kind."""
    codes = {
        kind: {n.reference_id for n in notifs if n.reference_type == kind and n.reference_id}
        for kind in ("request", "course")
    }
    ids = {
        "request": dict(
            db.query(Request.request_code, Request.id)
            .filter(Request.request_code.in_(codes["request"]))
            .all()
        ),
        "course": dict(
            db.query(Course.code, Course.id).filter(Course.code.in_(codes["course"])).all()
        ),
    }
    return [
        NotificationResponse(
            id=n.id,
            user_id=n.user_id,
            title=n.title,
            message=n.message,
            type=n.type,
            is_read=n.is_read,
            reference_type=n.reference_type,
            reference_id=n.reference_id,
            reference_record_id=ids.get(n.reference_type or "", {}).get(n.reference_id),
            created_at=n.created_at,
            time_ago=notification_service.format_time_ago(n.created_at),
        )
        for n in notifs
    ]


@router.get("", response_model=List[NotificationResponse])
def get_notifications(
    page: Page,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notifs = notification_service.get_user_notifications(
        db, current_user.id, page.limit, page.offset
    )
    return to_responses(db, notifs)


@router.patch("/{notification_id}", response_model=NotificationResponse)
def update_notification(
    notification_id: DatabaseID,
    payload: NotificationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notif = notification_service.mark_as_read(db, notification_id, current_user.id)
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notif.is_read = payload.is_read
    db.commit()
    return to_responses(db, [notif])[0]


@router.post("/read-all", response_model=ReadAllResponse)
def mark_all_read(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count = notification_service.mark_all_as_read(db, current_user.id)
    db.commit()
    return {"message": f"Marked {count} notifications as read", "count": count}


@router.get("/unread-count", response_model=NotificationCountResponse)
def unread_count(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return NotificationCountResponse(
        unread=notification_service.get_unread_count(db, current_user.id)
    )
