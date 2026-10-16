"""
Documentolog Enterprise Document Management Integration Adapter (Mocked Architecture Boundary)

In the production Jana Post architecture, approved employee HR requests (e.g., Vacation orders,
salary advance promissory notes) are forwarded to Documentolog (ЭДО / SED) for legal registration,
e-signatures (EDS / ЭЦП), and official corporate archiving.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from app.config import settings
from app.schemas.integration import AdapterTelemetry, DocumentologSyncResponse


class DocumentologAdapter:
    ADAPTER_NAME = "Documentolog (EDS / Corporate Electronic Document Flow)"
    MODE = "Mock Adapter (Synthetic Architecture Boundary)"

    def __init__(self):
        self.base_url = settings.MOCK_DOCUMENTOLOG_BASE_URL
        self.is_mock = True

    def get_telemetry(self) -> AdapterTelemetry:
        return AdapterTelemetry(
            adapter_name=self.ADAPTER_NAME,
            status="READY_MOCK",
            mode=self.MODE,
            endpoint_template=f"{self.base_url}/api/v2/documents/incoming_hr_request",
            synced_records_count=42,
            last_sync=datetime.now(timezone.utc),
            supported_operations=[
                "POST /api/v2/documents/register",
                "GET /api/v2/documents/{tracking_urn}/status",
                "POST /api/v2/signatures/verify_eds (Planned Future Phase)",
            ],
            notes="Receives approved HR requests from JanaMen for formal registration and corporate e-signature archiving.",
        )

    def register_approved_request(self, request_code: str, request_type: str, employee_name: str) -> DocumentologSyncResponse:
        """
        Mock handoff of an approved request to Documentolog.
        Generates an external tracking reference URN.
        """
        doc_num = request_code.replace("REQ-", "")
        tracking_urn = f"urn:doclog:janapost:hr:2026:{doc_num}"
        external_id = f"DOCLOG-2026-{doc_num}"

        return DocumentologSyncResponse(
            request_code=request_code,
            external_doc_id=external_id,
            tracking_urn=tracking_urn,
            status="REGISTERED_FOR_SIGNATURE",
            registered_at=datetime.now(timezone.utc),
            message=f"Document '{request_type}' successfully queued for e-document workflow in Documentolog.",
        )


documentolog_adapter = DocumentologAdapter()
