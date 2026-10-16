import random
from datetime import date, datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.enums import UserRole, RequestType, RequestStatus, RequestEventType, NotificationType
from app.models.user import User
from app.models.profile import EmployeeProfile
from app.models.request import Request, RequestEvent
from app.schemas.request import RequestCreate, RequestResponse, RequestDetailResponse, RequestEventResponse
from app.services.notification_service import notification_service
from app.services.audit_service import audit_service


class RequestService:
    @staticmethod
    def _calculate_business_days(start_date: date, end_date: Optional[date]) -> float:
        if not end_date or start_date == end_date:
            return 1.0
        # Calculate inclusive days
        delta = (end_date - start_date).days + 1
        return max(1.0, float(delta))

    @staticmethod
    def _format_submitted_date(dt: datetime) -> str:
        return dt.strftime("%d %b %Y")

    @staticmethod
    def _format_period_or_details(req: Request) -> str:
        if req.type == RequestType.VACATION:
            start_str = req.start_date.strftime("%d %b %Y")
            if req.end_date and req.end_date != req.start_date:
                end_str = req.end_date.strftime("%d %b %Y")
                return f"{start_str} – {end_str}"
            return f"Single day: {start_str}"
        elif req.type == RequestType.ADVANCE_PAYMENT:
            amount_str = f"{req.amount:,.0f} ₸" if req.amount else "Advance request"
            date_str = req.start_date.strftime("%d %b %Y")
            return f"{amount_str} (Requested for {date_str})"
        return f"{req.start_date}"

    @classmethod
    def to_response(cls, req: Request) -> RequestResponse:
        user_name = req.user.full_name if req.user else "Unknown"
        dept = req.user.profile.department if (req.user and req.user.profile) else "General"
        reviewer_name = req.reviewer.full_name if req.reviewer else None

        return RequestResponse(
            id=req.id,
            request_code=req.request_code,
            user_id=req.user_id,
            user_name=user_name,
            department=dept,
            type=req.type,
            start_date=req.start_date,
            end_date=req.end_date,
            amount=req.amount,
            reason=req.reason,
            status=req.status,
            reviewer_id=req.reviewer_id,
            reviewer_name=reviewer_name,
            review_comment=req.review_comment,
            external_sync_id=req.external_sync_id,
            submitted_date_formatted=cls._format_submitted_date(req.created_at),
            period_or_details=cls._format_period_or_details(req),
            created_at=req.created_at,
            updated_at=req.updated_at,
        )

    @classmethod
    def to_detail_response(cls, req: Request) -> RequestDetailResponse:
        base = cls.to_response(req)
        event_responses = []
        for e in req.events:
            actor_name = e.actor.full_name if e.actor else "System"
            event_responses.append(
                RequestEventResponse(
                    id=e.id,
                    actor_id=e.actor_id,
                    actor_name=actor_name,
                    event_type=e.event_type,
                    comment=e.comment,
                    created_at=e.created_at,
                )
            )
        return RequestDetailResponse(**base.model_dump(), events=event_responses)

    @classmethod
    def create_request(
        cls, db: Session, user: User, payload: RequestCreate, ip_address: Optional[str] = None
    ) -> Request:
        # 1. Validate Vacation Balance if applicable
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == user.id).first()
        if payload.type == RequestType.VACATION and profile:
            days_needed = cls._calculate_business_days(payload.start_date, payload.end_date)
            if profile.leave_balance_days < days_needed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient leave balance. You requested {days_needed:.1f} days, but only have {profile.leave_balance_days:.1f} days available.",
                )

        # 2. Generate unique request code
        last_req = db.query(Request).order_by(Request.id.desc()).first()
        next_num = 1045 if not last_req else (1000 + last_req.id + 1)
        req_code = f"REQ-{next_num}"

        # 3. Create request entity
        new_req = Request(
            request_code=req_code,
            user_id=user.id,
            type=payload.type,
            start_date=payload.start_date,
            end_date=payload.end_date,
            amount=payload.amount,
            reason=payload.reason,
            status=RequestStatus.PENDING,
            external_sync_id=f"DOCLOG-PENDING-{next_num}",
        )
        db.add(new_req)
        db.flush()

        # 4. Record initial event history
        initial_event = RequestEvent(
            request_id=new_req.id,
            actor_id=user.id,
            event_type=RequestEventType.SUBMITTED,
            comment=f"Submitted {payload.type.value} request. {payload.reason or 'No comment'}",
        )
        db.add(initial_event)

        # 5. Send persistent notifications
        # Notification to requester
        notification_service.create_notification(
            db=db,
            user_id=user.id,
            title="Request submitted",
            message=f"Your {payload.type.value} request ({req_code}) was submitted and sent to your manager for review.",
            type=NotificationType.REQUEST,
            reference_type="request",
            reference_id=req_code,
        )

        # Notification to Manager if exists
        if profile and profile.manager_id:
            notification_service.create_notification(
                db=db,
                user_id=profile.manager_id,
                title="New request awaiting your review",
                message=f"{user.full_name} submitted a {payload.type.value} request ({req_code}).",
                type=NotificationType.REQUEST,
                reference_type="request",
                reference_id=req_code,
            )

        # 6. Audit logging
        audit_service.log_event(
            db=db,
            action="REQUEST_SUBMITTED",
            actor_id=user.id,
            target_type="request",
            target_id=req_code,
            details={"type": payload.type.value, "start": str(payload.start_date), "end": str(payload.end_date)},
            ip_address=ip_address,
        )

        db.commit()
        db.refresh(new_req)
        return new_req

    @classmethod
    def get_user_requests(
        cls,
        db: Session,
        user: User,
        status_filter: Optional[RequestStatus] = None,
        type_filter: Optional[RequestType] = None,
    ) -> List[Request]:
        query = db.query(Request).filter(Request.user_id == user.id)
        if status_filter:
            query = query.filter(Request.status == status_filter)
        if type_filter:
            query = query.filter(Request.type == type_filter)
        return query.order_by(Request.created_at.desc()).all()

    @classmethod
    def get_team_requests(
        cls,
        db: Session,
        manager: User,
        status_filter: Optional[RequestStatus] = None,
    ) -> List[Request]:
        """Returns requests from direct reports of the manager."""
        report_user_ids = [
            p.user_id
            for p in db.query(EmployeeProfile).filter(EmployeeProfile.manager_id == manager.id).all()
        ]
        
        # If no direct reports, return empty list (prevents leaking all records)
        if not report_user_ids:
            return []

        query = db.query(Request).filter(Request.user_id.in_(report_user_ids))
        if status_filter:
            query = query.filter(Request.status == status_filter)
        return query.order_by(Request.created_at.desc()).all()

    @classmethod
    def get_request_by_id(cls, db: Session, request_id: int, user: User) -> Request:
        req = db.query(Request).filter(Request.id == request_id).first()
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        # Authorization check:
        # Employee can only see own request.
        # Manager can only see own request or request of direct reports.
        # HR Admin can see all.
        if user.role == UserRole.EMPLOYEE and req.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this request")
        
        if user.role == UserRole.MANAGER and req.user_id != user.id:
            requester_profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == req.user_id).first()
            if not requester_profile or requester_profile.manager_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. This request does not belong to your assigned team."
                )

        return req

    @classmethod
    def review_request(
        cls,
        db: Session,
        request_id: int,
        reviewer: User,
        action: str,
        comment: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Request:
        req = db.query(Request).filter(Request.id == request_id).first()
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        if req.status != RequestStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Request is already resolved with status '{req.status.value}' and cannot be modified.",
            )

        # RBAC Check:
        # Employee CANNOT approve/reject requests (including their own).
        if reviewer.role == UserRole.EMPLOYEE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Employees cannot approve or reject requests.",
            )

        # Manager can ONLY review requests for their direct reports.
        if reviewer.role == UserRole.MANAGER:
            requester_profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == req.user_id).first()
            if not requester_profile or requester_profile.manager_id != reviewer.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. You can only review requests submitted by your direct reports.",
                )

        # Update status
        new_status = RequestStatus.APPROVED if action == "approve" else RequestStatus.REJECTED
        event_type = RequestEventType.APPROVED if action == "approve" else RequestEventType.REJECTED

        req.status = new_status
        req.reviewer_id = reviewer.id
        req.review_comment = comment
        req.updated_at = datetime.now(timezone.utc)

        # If approved, update external integration reference ID (Mock Documentolog handoff)
        if new_status == RequestStatus.APPROVED:
            req.external_sync_id = f"DOCLOG-2026-{1000 + req.id}"
            # Deduct leave days if Vacation
            if req.type == RequestType.VACATION:
                profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == req.user_id).first()
                if profile:
                    days = cls._calculate_business_days(req.start_date, req.end_date)
                    profile.leave_balance_days = max(0.0, profile.leave_balance_days - days)

        # Add event record
        event = RequestEvent(
            request_id=req.id,
            actor_id=reviewer.id,
            event_type=event_type,
            comment=comment or f"Request was {new_status.value.lower()} by {reviewer.full_name}",
        )
        db.add(event)

        # Send persistent notification to requester
        notification_service.create_notification(
            db=db,
            user_id=req.user_id,
            title=f"Request {new_status.value}",
            message=f"Your {req.type.value} request ({req.request_code}) was {new_status.value.lower()} by {reviewer.full_name}. {comment or ''}".strip(),
            type=NotificationType.REQUEST,
            reference_type="request",
            reference_id=req.request_code,
        )

        # Audit logging
        audit_service.log_event(
            db=db,
            action=f"REQUEST_{new_status.value.upper()}",
            actor_id=reviewer.id,
            target_type="request",
            target_id=req.request_code,
            details={"action": action, "comment": comment, "new_status": new_status.value},
            ip_address=ip_address,
        )

        db.commit()
        db.refresh(req)
        return req


request_service = RequestService()
