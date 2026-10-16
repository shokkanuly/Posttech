from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class AdapterTelemetry(BaseModel):
    adapter_name: str
    status: str  # "READY_MOCK", "CONNECTED", "ERROR"
    mode: str = "Mock Adapter (Synthetic Architecture Boundary)"
    endpoint_template: str
    synced_records_count: int
    last_sync: datetime
    supported_operations: List[str]
    notes: str


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
