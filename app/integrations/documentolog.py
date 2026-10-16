"""Unconnected boundary. Optional local IDs are explicitly marked MOCK."""

from datetime import datetime, timezone

from app.config import settings
from app.schemas.integration import AdapterTelemetry, DocumentologSyncResponse


class DocumentologAdapter:
    def get_telemetry(self):
        return AdapterTelemetry(
            adapter_name="Documentolog",
            status="UNCONNECTED",
            mode="Unconnected; local simulation only"
            if settings.ENABLE_MOCK_INTEGRATIONS
            else "Unconnected",
            endpoint_template="Not configured",
            synced_records_count=0,
            last_sync=None,
            supported_operations=[],
            notes="No credentials, approved connection, document registration or signature service is configured.",
        )

    def register_approved_request(self, request_code: str, request_type: str, employee_name: str):
        if not settings.ENABLE_MOCK_INTEGRATIONS:
            raise RuntimeError("Documentolog is unconnected")
        return DocumentologSyncResponse(
            request_code=request_code,
            external_doc_id=f"MOCK-DOCLOG-{request_code}",
            tracking_urn=f"urn:mock:{request_code}",
            status="LOCAL_SIMULATION_ONLY",
            registered_at=datetime.now(timezone.utc),
            message="Synthetic local reference. No external registration occurred.",
        )


documentolog_adapter = DocumentologAdapter()
