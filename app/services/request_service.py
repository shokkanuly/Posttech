import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, cast
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session, joinedload

from app import leave_calendar
from app.config import settings
from app.integrations import outbox
from app.integrations.documentolog import documentolog_adapter
from app.integrations.one_c_zup import one_c_adapter
from app.models.enums import (
    NotificationType,
    RequestEventType,
    RequestStatus,
    RequestType,
    UserRole,
)
from app.models.profile import EmployeeProfile
from app.models.request import Request, RequestEvent
from app.models.user import User
from app.schemas.request import (
    LeaveDay,
    ProfileChanges,
    RequestCreate,
    RequestDetailResponse,
    RequestEventResponse,
    RequestResponse,
)
from app.services.audit_service import audit_service
from app.services.notification_service import notification_service

KAZAKHSTAN = timezone(timedelta(hours=5))  # single national time zone since March 2024


def request_today() -> date:
    """Business date for request rules; tests pin it so fixed dates never expire."""
    return datetime.now(KAZAKHSTAN).date()


class RequestService:
    @staticmethod
    def _calculate_calendar_days(start_date: date, end_date: Optional[date]) -> float:
        # Local calendar with explicitly configured exclusions; 1C is unconnected.
        return one_c_adapter.vacation_days(start_date, end_date)

    @classmethod
    def leave_summary(cls, db: Session, user_ids: list[int]) -> dict[int, dict[str, float]]:
        """Approved (used) and pending vacation days per employee, by the same day rule."""
        summary = {uid: {"used_days": 0.0, "pending_days": 0.0} for uid in user_ids}
        rows = (
            db.query(Request)
            .filter(
                Request.user_id.in_(user_ids),
                Request.type == RequestType.VACATION,
                Request.status.in_([RequestStatus.PENDING, RequestStatus.APPROVED]),
            )
            .all()
        )
        for r in rows:
            key = "used_days" if r.status == RequestStatus.APPROVED else "pending_days"
            summary[r.user_id][key] += (
                r.charged_leave_days
                if r.status == RequestStatus.APPROVED and r.charged_leave_days is not None
                else cls._calculate_calendar_days(r.start_date, r.end_date)
            )
        return summary

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
            amount_str = f"{req.amount:,.2f} ₸" if req.amount else "Advance request"
            date_str = req.start_date.strftime("%d %b %Y")
            return f"{amount_str} (Requested for {date_str})"
        elif req.type == RequestType.PROFILE_UPDATE:
            return ", ".join(req.profile_changes or {})
        return f"{req.start_date}"

    @classmethod
    def to_response(cls, req: Request) -> RequestResponse:
        user_name = req.user.full_name if req.user else "Unknown"
        dept = req.user.profile.department if (req.user and req.user.profile) else "General"
        reviewer_name = req.reviewer.full_name if req.reviewer else None
        days = (
            leave_calendar.breakdown(req.start_date, req.end_date)
            if req.type == RequestType.VACATION
            else None
        )

        return RequestResponse(
            id=req.id,
            request_code=req.request_code,
            user_id=req.user_id,
            user_name=user_name,
            department=dept,
            type=req.type,
            start_date=req.start_date,
            end_date=req.end_date,
            amount=float(req.amount) if req.amount is not None else None,
            reason=req.reason,
            status=req.status,
            reviewer_id=req.reviewer_id,
            reviewer_name=reviewer_name,
            review_comment=req.review_comment,
            external_sync_id=req.external_sync_id,
            external_ref=req.external_sync_id,
            sync_status=req.integration_status or "NOT_REQUIRED",
            integration_mode=req.integration_mode,
            submitted_date_formatted=cls._format_submitted_date(req.created_at),
            period_or_details=cls._format_period_or_details(req),
            vacation_days=(
                req.charged_leave_days
                if req.charged_leave_days is not None
                else cls._calculate_calendar_days(req.start_date, req.end_date)
            )
            if req.type == RequestType.VACATION
            else None,
            weekend_days=sum(d["kind"] == "weekend" for d in days) if days else None,
            holiday_days=sum(d["kind"] == "holiday" for d in days) if days else None,
            profile_changes=req.profile_changes,
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
        leave_days = (
            [LeaveDay(**d) for d in leave_calendar.breakdown(req.start_date, req.end_date)]
            if req.type == RequestType.VACATION
            else []
        )
        return RequestDetailResponse(
            **base.model_dump(), events=event_responses, leave_days=leave_days
        )

    @classmethod
    def leave_preview(cls, db: Session, user: User, start: date, end: date) -> dict:
        """Marked days of a planned vacation and what the employee can still take."""
        if end < start or (end - start).days > settings.REQUEST_HORIZON_DAYS:
            raise HTTPException(422, "Choose an end date on or after the start date")
        days = leave_calendar.breakdown(start, end)
        balance = user.profile.leave_balance_days if user.profile else 0.0
        pending = cls.leave_summary(db, [user.id])[user.id]["pending_days"]
        return {
            "days": days,
            "calendar_days": len(days),
            "weekend_days": sum(d["kind"] == "weekend" for d in days),
            "holiday_days": sum(d["kind"] == "holiday" for d in days),
            "charged_days": cls._calculate_calendar_days(start, end),
            "available_days": max(0.0, balance - pending),
        }

    @classmethod
    def create_request(
        cls,
        db: Session,
        user: User,
        payload: RequestCreate,
        ip_address: Optional[str] = None,
        idempotency_key: str | None = None,
        actor: Optional[User] = None,
    ) -> Request:
        """actor: a manager/HR filing on the employee's behalf; they decide it right after."""
        # 1. Validate Vacation Balance if applicable
        # Serialize reservations for this employee on both SQLite and PostgreSQL.
        # An UPDATE locks the row until commit, before checking balance or overlaps.
        db.execute(
            update(EmployeeProfile)
            .where(EmployeeProfile.user_id == user.id)
            .values(leave_balance_days=EmployeeProfile.leave_balance_days)
        )
        profile = (
            db.query(EmployeeProfile)
            .populate_existing()
            .filter(EmployeeProfile.user_id == user.id)
            .first()
        )
        if not profile:
            raise HTTPException(409, "An HR profile is required before submitting a request")
        canonical = payload.model_dump(mode="json")
        if payload.type != RequestType.PROFILE_UPDATE:
            # Preserve hashes persisted before the profile-update field existed.
            canonical.pop("profile_changes", None)
        canonical["amount"] = (
            str(payload.amount.quantize(Decimal("0.01"))) if payload.amount is not None else None
        )
        canonical["reason"] = payload.reason or None
        submission_hash = hashlib.sha256(
            json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if idempotency_key:
            existing = (
                db.query(Request).filter_by(user_id=user.id, submission_key=idempotency_key).first()
            )
            if existing:
                if existing.submission_hash != submission_hash:
                    raise HTTPException(409, "Submission key already used with different content")
                db.commit()
                return existing
        assigned_reviewer = (
            db.query(User)
            .filter(
                User.id == profile.manager_id,
                User.id != user.id,
                User.is_active.is_(True),
                User.role.in_([UserRole.MANAGER, UserRole.HR_ADMIN]),
            )
            .first()
            if profile.manager_id is not None
            else None
        )
        reviewers = (
            [assigned_reviewer]
            if assigned_reviewer
            else db.query(User)
            .filter(User.role == UserRole.HR_ADMIN, User.is_active.is_(True), User.id != user.id)
            .all()
        )
        review_destination = "your manager" if assigned_reviewer else "HR"
        current = request_today()
        start = payload.start_date or current  # a profile update is dated today
        if start < current:
            raise HTTPException(422, "Start date cannot be in the past")
        if (payload.end_date or start) > current + timedelta(days=settings.REQUEST_HORIZON_DAYS):
            raise HTTPException(422, "Request dates exceed the configured planning horizon")
        if (
            payload.type == RequestType.ADVANCE_PAYMENT
            and payload.amount is not None
            and float(payload.amount) > settings.MAX_ADVANCE_AMOUNT
        ):
            raise HTTPException(422, "Advance amount exceeds the allowed maximum")
        if payload.type == RequestType.PROFILE_UPDATE:
            # Personal data comes only from 1C:ZUP and Documentolog; the profile is read-only.
            raise HTTPException(
                409,
                "Profile data is kept in 1C and Documentolog and is read-only here; contact HR to correct it",
            )
        if payload.type == RequestType.VACATION:
            days_needed = cls._calculate_calendar_days(start, payload.end_date)
            if days_needed == 0:
                raise HTTPException(422, "The selected dates are excluded from the leave calendar")
            active_vacations = (
                db.query(Request)
                .filter(
                    Request.user_id == user.id,
                    Request.type == RequestType.VACATION,
                    Request.status.in_([RequestStatus.PENDING, RequestStatus.APPROVED]),
                )
                .all()
            )
            new_end = payload.end_date or start
            if any(
                r.start_date <= new_end and (r.end_date or r.start_date) >= start
                for r in active_vacations
            ):
                raise HTTPException(409, "These dates overlap another active vacation request")
            # Pending requests are reserved, so the balance cannot be promised twice.
            reserved = sum(
                cls._calculate_calendar_days(r.start_date, r.end_date)
                for r in active_vacations
                if r.status == RequestStatus.PENDING
            )
            if profile.leave_balance_days - reserved < days_needed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient leave balance. You requested {days_needed:.1f} days, but only have {max(0.0, profile.leave_balance_days - reserved):.1f} days available.",
                )

        # The final code is allocated from the database identity in a new namespace.
        req_code = f"PENDING-{uuid4().hex}"

        # 3. Create request entity
        new_req = Request(
            request_code=req_code,
            user_id=user.id,
            type=payload.type,
            start_date=start,
            end_date=payload.end_date,
            amount=payload.amount,
            reason=payload.reason,
            submission_key=idempotency_key,
            submission_hash=submission_hash if idempotency_key else None,
            status=RequestStatus.PENDING,
            external_sync_id=None,
        )
        db.add(new_req)
        db.flush()
        req_code = f"REQ-N{new_req.id:06d}"
        new_req.request_code = req_code

        # 4. Record initial event history
        initial_event = RequestEvent(
            request_id=new_req.id,
            actor_id=(actor or user).id,
            event_type=RequestEventType.SUBMITTED,
            comment=f"Submitted {payload.type.value} request. {payload.reason or 'No comment'}",
        )
        db.add(initial_event)

        # 5. Send persistent notifications
        # Notification to requester
        if not actor:  # a filer decides right away; the decision notification tells the employee
            notification_service.create_notification(
                db=db,
                user_id=user.id,
                title="Request submitted",
                message=(
                    f"Your {payload.type.value} request ({req_code}) was submitted and sent to {review_destination} for review."
                    if reviewers
                    else f"Your {payload.type.value} request ({req_code}) was submitted. An authorized reviewer must be configured; contact HR."
                ),
                type=NotificationType.REQUEST,
                reference_type="request",
                reference_id=req_code,
            )

        # Notify only active, authorized reviewers; HR covers missing/unavailable managers.
        for reviewer in [] if actor else reviewers:
            notification_service.create_notification(
                db=db,
                user_id=reviewer.id,
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
            actor_id=(actor or user).id,
            target_type="request",
            target_id=req_code,
            details={
                "type": payload.type.value,
                "start": str(start),
                "end": str(payload.end_date),
            },
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
        limit: int = 50,
        offset: int = 0,
    ) -> List[Request]:
        query = (
            db.query(Request)
            .options(
                joinedload(Request.user).joinedload(User.profile), joinedload(Request.reviewer)
            )
            .filter(Request.user_id == user.id)
        )
        if status_filter:
            query = query.filter(Request.status == status_filter)
        if type_filter:
            query = query.filter(Request.type == type_filter)
        return (
            query.order_by(Request.created_at.desc(), Request.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    @classmethod
    def get_team_requests(
        cls,
        db: Session,
        manager: User,
        status_filter: Optional[RequestStatus] = None,
        type_filter: Optional[RequestType] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Request]:
        """Returns requests from direct reports of the manager."""
        query = db.query(Request).options(
            joinedload(Request.user).joinedload(User.profile), joinedload(Request.reviewer)
        )
        if manager.role != UserRole.HR_ADMIN:
            query = query.join(EmployeeProfile, EmployeeProfile.user_id == Request.user_id).filter(
                EmployeeProfile.manager_id == manager.id
            )
        if status_filter:
            query = query.filter(Request.status == status_filter)
        if type_filter:
            query = query.filter(Request.type == type_filter)
        return (
            query.order_by(Request.created_at.desc(), Request.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

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
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this request"
            )

        if user.role == UserRole.MANAGER and req.user_id != user.id:
            requester_profile = (
                db.query(EmployeeProfile).filter(EmployeeProfile.user_id == req.user_id).first()
            )
            if not requester_profile or requester_profile.manager_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. This request does not belong to your assigned team.",
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
        if action not in {"approve", "reject"}:
            raise HTTPException(422, "Action must be approve or reject")
        req = cls.get_request_by_id(db, request_id, reviewer)
        if reviewer.role == UserRole.EMPLOYEE:
            raise HTTPException(403, "Employees cannot approve or reject requests.")
        if req.user_id == reviewer.id:
            raise HTTPException(403, "You cannot review your own request")

        new_status = RequestStatus.APPROVED if action == "approve" else RequestStatus.REJECTED
        event_type = RequestEventType.APPROVED if action == "approve" else RequestEventType.REJECTED
        # Conditional update serializes competing reviews, including on SQLite.
        changed = db.execute(
            update(Request)
            .where(
                Request.id == request_id,
                Request.status == RequestStatus.PENDING,
            )
            .values(
                status=new_status,
                reviewer_id=reviewer.id,
                review_comment=comment,
                updated_at=datetime.now(timezone.utc),
            ),
            execution_options={"synchronize_session": False},
        )
        if cast(CursorResult, changed).rowcount != 1:
            db.rollback()
            raise HTTPException(409, "Request is already resolved and cannot be modified")

        if new_status == RequestStatus.APPROVED and req.type == RequestType.VACATION:
            days = cls._calculate_calendar_days(req.start_date, req.end_date)
            debit = db.execute(
                update(EmployeeProfile)
                .where(
                    EmployeeProfile.user_id == req.user_id,
                    EmployeeProfile.leave_balance_days >= days,
                )
                .values(leave_balance_days=EmployeeProfile.leave_balance_days - days),
                execution_options={"synchronize_session": False},
            )
            if cast(CursorResult, debit).rowcount != 1:
                db.rollback()
                raise HTTPException(400, "Insufficient leave balance at approval")

        db.refresh(req)
        approved = new_status == RequestStatus.APPROVED
        if approved and req.type == RequestType.VACATION:
            req.charged_leave_days = days
            req.leave_balance_confirmed = False
        if approved and req.type == RequestType.PROFILE_UPDATE and req.user.profile:
            for field, change in (req.profile_changes or {}).items():
                if field in ProfileChanges.model_fields:
                    setattr(req.user.profile, field, change["to"])
        document = approved and req.type in {RequestType.VACATION, RequestType.ADVANCE_PAYMENT}
        if document and settings.INTEGRATION_GATEWAY_URL:
            req.integration_status = "PENDING"
            outbox.enqueue(db, req)
        if document and settings.ENABLE_MOCK_INTEGRATIONS and not settings.INTEGRATION_GATEWAY_URL:
            # Pure local simulation, never an external document registration.
            simulated = documentolog_adapter.register_approved_request(
                req.request_code, req.type.value, req.user.full_name
            )
            req.external_sync_id = simulated.external_doc_id

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
            details={"action": action, "new_status": new_status.value},
            ip_address=ip_address,
        )

        db.commit()
        db.refresh(req)
        return req


request_service = RequestService()
