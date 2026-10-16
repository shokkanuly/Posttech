from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.enums import NotificationType
from app.models.notification import Notification


class NotificationService:
    @staticmethod
    def create_notification(
        db: Session,
        user_id: int,
        title: str,
        message: str,
        type: NotificationType = NotificationType.SYSTEM,
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=type,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        db.add(notification)
        db.flush()
        return notification

    @staticmethod
    def get_user_notifications(
        db: Session, user_id: int, limit: int = 50, offset: int = 0
    ) -> List[Notification]:
        return (
            db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_unread_count(db: Session, user_id: int) -> int:
        return (
            db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.is_read.is_(False))
            .count()
        )

    @staticmethod
    def mark_as_read(db: Session, notification_id: int, user_id: int) -> Optional[Notification]:
        notif = (
            db.query(Notification)
            .filter(Notification.id == notification_id, Notification.user_id == user_id)
            .first()
        )
        if notif:
            notif.is_read = True
            db.flush()
        return notif

    @staticmethod
    def mark_all_as_read(db: Session, user_id: int) -> int:
        count = (
            db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.is_read.is_(False))
            .update({"is_read": True})
        )
        db.flush()
        return count

    @staticmethod
    def format_time_ago(dt: datetime) -> str:
        """Helper to format datetime into human readable relative time."""
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = now - dt
        seconds = int(diff.total_seconds())

        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} min ago" if minutes == 1 else f"{minutes} mins ago"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour ago" if hours == 1 else f"{hours} hours ago"
        else:
            days = seconds // 86400
            return f"{days} day ago" if days == 1 else f"{days} days ago"


notification_service = NotificationService()
