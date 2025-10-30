"""Schema for notification details."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class NotificationDetail(BaseModel):
    """Schema for notification details."""

    model_config = ConfigDict(from_attributes=True)

    notification_id: UUID
    recipient_email: EmailStr
    subject: str
    message: str
    notification_type: str
    status: str
    error_message: str
    retry_count: int
    max_retries: int
    created_at: datetime
    queued_at: datetime | None
    sent_at: datetime | None
    failed_at: datetime | None
    metadata: dict[str, Any] | None
    recipient_id: UUID | None
