from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from app.schemas.common import UTCDateTime


class AdapterTelemetry(BaseModel):
    adapter_name: str
    status: str  # "READY_MOCK", "CONNECTED", "ERROR"
    mode: str = "Mock Adapter (Synthetic Architecture Boundary)"
    endpoint_template: str
    synced_records_count: int
    last_sync: Optional[UTCDateTime] = None
    supported_operations: List[str]
    notes: str
    pending_count: int = 0
    failed_count: int = 0
    last_success: Optional[UTCDateTime] = None
    last_error: Optional[str] = None


class DocumentologSyncResponse(BaseModel):
    request_code: str
    external_doc_id: str
    tracking_urn: str
    status: str
    registered_at: datetime
    message: str


class OneCProfileSyncResponse(BaseModel):
    employee_code: str
    external_1c_id: str
    leave_balance_verified: float
    sync_status: str
    timestamp: datetime
