import json
from typing import Optional, Any
from sqlalchemy.orm import Session
from app.models.audit import AuditEvent


class AuditService:
    @staticmethod
    def log_event(
        db: Session,
        action: str,
        actor_id: Optional[int] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        details: Optional[Any] = None,
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """Create a persistent immutable audit record."""
        details_str = json.dumps(details, default=str) if details is not None else None
        event = AuditEvent(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            details_json=details_str,
            ip_address=ip_address,
        )
        db.add(event)
        db.flush()
        return event


audit_service = AuditService()
