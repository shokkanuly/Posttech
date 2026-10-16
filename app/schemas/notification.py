from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationType
from app.schemas.common import UTCDateTime


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    type: NotificationType
    is_read: bool
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    created_at: UTCDateTime
    time_ago: str

    model_config = ConfigDict(from_attributes=True)


class NotificationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    is_read: bool
