from datetime import datetime
from typing import List, Optional

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.schemas.common import BodyDatabaseID, UTCDateTime


class RetryDelivery(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_retry_count: int = Field(ge=0, strict=True)
    reason: str = Field(min_length=3, max_length=500)


class ResolveProfileReview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    observed_at: AwareDatetime
    user_id: BodyDatabaseID | None = None
    reason: str = Field(min_length=3, max_length=500)


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
