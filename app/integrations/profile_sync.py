"""Single writer for external HR snapshots; no names/emails are used for matching."""

from datetime import datetime, timedelta, timezone
from typing import cast
from urllib.parse import urlencode

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import or_, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.integrations.contracts import EmployeePage, EmployeeSnapshot, GatewayHealth
from app.integrations.outbox import aware, gateway_request
from app.models.enums import RequestStatus, UserRole
from app.models.integration import IntegrationReview, IntegrationSyncState
from app.models.profile import EmployeeProfile
from app.models.request import Request
from app.services.audit_service import audit_service


def state_for(db: Session) -> IntegrationSyncState:
    state = db.get(IntegrationSyncState, "one_c")
    if state is None:
        state = IntegrationSyncState(name="one_c", mode="UNCONNECTED", records_count=0)
        db.add(state)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            state = db.get(IntegrationSyncState, "one_c")
            assert state is not None
    return state


def review(db: Session, code: str, reason: str) -> None:
    row = db.get(IntegrationReview, code)
    if row is None:
        db.add(
            IntegrationReview(
                employee_code=code, reason=reason, observed_at=datetime.now(timezone.utc)
            )
        )
    else:
        row.reason, row.observed_at = reason, datetime.now(timezone.utc)


def apply_snapshot(db: Session, snapshot: EmployeeSnapshot, mode: str) -> bool:
    """The only integration writer of profile facts; callers must use a verified gateway."""
    # Lock in the same way as request submission/approval on both supported databases.
    db.execute(
        update(EmployeeProfile)
        .where(EmployeeProfile.employee_code == snapshot.employee_code)
        .values(leave_balance_days=EmployeeProfile.leave_balance_days)
    )
    profile = (
        db.query(EmployeeProfile)
        .populate_existing()
        .filter_by(employee_code=snapshot.employee_code)
        .first()
    )
    if profile is None:
        review(db, snapshot.employee_code, "UNKNOWN_EMPLOYEE")
        return False
    if profile.source_as_of and aware(profile.source_as_of) > snapshot.as_of:
        review(db, snapshot.employee_code, "STALE_SNAPSHOT")
        return False
    manager_id = None
    if snapshot.manager_employee_code:
        manager = (
            db.query(EmployeeProfile)
            .filter_by(employee_code=snapshot.manager_employee_code)
            .first()
        )
        if (
            manager is None
            or manager.user_id == profile.user_id
            or not manager.user.is_active
            or manager.user.role not in {UserRole.MANAGER, UserRole.HR_ADMIN}
        ):
            review(db, snapshot.employee_code, "UNKNOWN_MANAGER")
            return False
        manager_id = manager.user_id
    outstanding = (
        db.query(Request)
        .filter(
            Request.user_id == profile.user_id,
            Request.status == RequestStatus.APPROVED,
            Request.leave_balance_confirmed.is_(False),
        )
        .all()
    )
    provisional = sum(
        req.charged_leave_days or 0
        for req in outstanding
        if req.request_code not in snapshot.confirmed_request_codes
    )
    if snapshot.leave_balance_days < provisional:
        review(db, snapshot.employee_code, "BALANCE_CONFLICT")
        return False
    for req in outstanding:
        if req.request_code in snapshot.confirmed_request_codes:
            req.leave_balance_confirmed = True
    profile.user.full_name = snapshot.full_name
    profile.company, profile.department, profile.position = (
        snapshot.company,
        snapshot.department,
        snapshot.position,
    )
    profile.manager_id, profile.hire_date = manager_id, snapshot.hire_date
    profile.source_mode, profile.source_balance_days = mode, snapshot.leave_balance_days
    profile.source_as_of, profile.synced_at = snapshot.as_of, datetime.now(timezone.utc)
    profile.leave_balance_days = snapshot.leave_balance_days - provisional
    old = db.get(IntegrationReview, snapshot.employee_code)
    if old:
        db.delete(old)
    return True


def sync_profiles(db: Session, force: bool = False) -> dict:
    if not settings.INTEGRATION_GATEWAY_URL:
        return {"status": "disabled", "mode": "UNCONNECTED", "updated": 0}
    state = state_for(db)
    now = datetime.now(timezone.utc)
    interval = (
        settings.INTEGRATION_REFRESH_COOLDOWN_SECONDS
        if force
        else settings.INTEGRATION_SYNC_INTERVAL_SECONDS
    )
    cursor = aware(state.cursor).isoformat() if state.cursor and not force else None
    changed = db.execute(
        update(IntegrationSyncState)
        .where(
            IntegrationSyncState.name == "one_c",
            or_(
                IntegrationSyncState.last_attempt_at.is_(None),
                IntegrationSyncState.last_attempt_at <= now - timedelta(seconds=interval),
            ),
        )
        .values(last_attempt_at=now),
        execution_options={"synchronize_session": False},
    )
    if cast(CursorResult, changed).rowcount != 1:
        db.rollback()
        if force:
            raise HTTPException(429, "Profile refresh is rate-limited")
        return {"status": "not_due", "mode": state.mode, "updated": 0}
    db.commit()
    health_code, health = gateway_request("GET", "/health")
    observed_mode = None
    try:
        if health_code != 200:
            raise ValueError
        live = GatewayHealth.model_validate(health)
        observed_mode = live.mode
        path = "/v1/employees" + ("?" + urlencode({"updated_since": cursor}) if cursor else "")
        code, data = gateway_request("GET", path)
        if code != 200:
            raise ValueError
        page = EmployeePage.model_validate(data)
        if page.mode != live.mode or (cursor and page.next_cursor < datetime.fromisoformat(cursor)):
            raise ValueError
        if any(row.as_of > page.next_cursor for row in page.employees):
            raise ValueError
    except (ValueError, ValidationError):
        db.rollback()
        state = state_for(db)
        if observed_mode:
            state.mode = observed_mode
        state.last_error = "GATEWAY_UNAVAILABLE"
        db.commit()
        return {"status": "unavailable", "mode": state.mode, "updated": 0}
    updated = sum(apply_snapshot(db, snapshot, page.mode) for snapshot in page.employees)
    state = state_for(db)
    state.mode, state.cursor = page.mode, page.next_cursor
    state.last_success_at, state.last_error = now, None
    state.records_count = (
        db.query(EmployeeProfile).filter(EmployeeProfile.source_mode == page.mode).count()
    )
    audit_service.log_event(
        db,
        action="INTEGRATION_PROFILE_SYNC",
        target_type="integration",
        details={"mode": page.mode, "updated_count": updated},
    )
    db.commit()
    return {"status": "ok", "mode": page.mode, "updated": updated}


def profile_metadata(db: Session, profile: EmployeeProfile) -> dict:
    state = db.get(IntegrationSyncState, "one_c")
    checked_at = state.last_success_at if state and state.last_success_at else profile.synced_at
    stale = bool(
        (settings.INTEGRATION_GATEWAY_URL or profile.source_mode != "LOCAL")
        and (
            not settings.INTEGRATION_GATEWAY_URL
            or not checked_at
            or (state and state.last_error)
            or aware(checked_at)
            < datetime.now(timezone.utc)
            - timedelta(seconds=2 * settings.INTEGRATION_SYNC_INTERVAL_SECONDS)
        )
    )
    return {
        "data_source": "MOCK 1C snapshot; not official HR data"
        if profile.source_mode == "MOCK"
        else "Local HR records; 1C is unconnected",
        "source_mode": profile.source_mode,
        "synced_at": profile.synced_at,
        "as_of": profile.source_as_of,
        "is_stale": stale,
        "is_official_hr_data": False,
    }
