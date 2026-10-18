"""HR-only telemetry from persisted state; no network requests while rendering cards."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.integration import IntegrationOutbox, IntegrationSyncState
from app.models.profile import EmployeeProfile
from app.models.request import Request
from app.schemas.integration import AdapterTelemetry


def integrations(db: Session) -> list[AdapterTelemetry]:
    state = db.get(IntegrationSyncState, "one_c")
    pending = (
        db.query(IntegrationOutbox)
        .filter(IntegrationOutbox.status.in_(["PENDING", "SENT"]))
        .count()
    )
    failed = (
        db.query(IntegrationOutbox).filter(IntegrationOutbox.status.in_(["FAILED", "DEAD"])).count()
    )
    last_registered = (
        db.query(func.max(Request.integration_completed_at))
        .filter(Request.integration_status == "REGISTERED")
        .scalar()
    )
    observed_mock = db.query(Request).filter(
        Request.integration_mode == "MOCK"
    ).first() is not None or bool(state and state.mode == "MOCK")
    enabled = bool(settings.INTEGRATION_GATEWAY_URL)
    mode = "MOCK" if enabled and observed_mock else "UNCONNECTED"
    notes = (
        "MOCK gateway only. Synthetic connectors; no live 1C or Documentolog connection."
        if enabled
        else "Gateway disabled. Local synthetic records; no enterprise connection."
    )
    return [
        AdapterTelemetry(
            adapter_name="1C:ZUP",
            status=mode,
            mode=mode,
            endpoint_template="/v1/employees" if enabled else "Not configured",
            synced_records_count=db.query(EmployeeProfile)
            .filter(EmployeeProfile.source_mode == "MOCK")
            .count(),
            last_sync=state.last_success_at if state else None,
            last_success=state.last_success_at if state else None,
            pending_count=0,
            failed_count=0,
            last_error=state.last_error if state else None,
            supported_operations=["MOCK_READ_SNAPSHOTS"] if mode == "MOCK" else [],
            notes=notes,
        ),
        AdapterTelemetry(
            adapter_name="Documentolog",
            status=mode,
            mode=mode,
            endpoint_template="/v1/documents" if enabled else "Not configured",
            synced_records_count=db.query(Request)
            .filter(Request.integration_status == "REGISTERED", Request.integration_mode == "MOCK")
            .count(),
            last_sync=last_registered,
            last_success=last_registered,
            pending_count=pending,
            failed_count=failed,
            supported_operations=["MOCK_REGISTER_DOCUMENT"] if mode == "MOCK" else [],
            notes=notes,
        ),
    ]
