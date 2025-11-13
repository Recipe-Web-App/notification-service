"""Schema for notification details."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import EmailStr, Field

from core.schemas.base_schema_model import BaseSchemaModel


class NotificationDetail(BaseSchemaModel):
    """Schema for notification details.

    The message field is optional and can be excluded from the response
    to reduce payload size. Use the include_message parameter when
    fetching notifications to include the full message body.
    """

    notification_id: UUID = Field(
        ..., description="Unique identifier for the notification"
    )
    recipient_email: EmailStr = Field(
        ..., description="Email address of the notification recipient"
    )
    subject: str = Field(
        ..., min_length=1, description="Subject line of the notification"
    )
    message: str | None = Field(
        None, description="Full message body (optional, may be excluded for brevity)"
    )
    notification_type: str = Field(
        ...,
        min_length=1,
        description="Type of notification (e.g., WELCOME, PASSWORD_RESET)",
    )
    status: str = Field(
        ...,
        min_length=1,
        description="Current status (e.g., PENDING, SENT, FAILED)",
    )
    error_message: str = Field(
        ..., description="Error message if failed (empty string if no error)"
    )
    retry_count: int = Field(
        ..., ge=0, description="Number of times notification was retried"
    )
    max_retries: int = Field(
        ..., ge=0, description="Maximum number of retry attempts allowed"
    )
    created_at: datetime = Field(
        ..., description="Timestamp when the notification was created"
    )
    queued_at: datetime | None = Field(
        None, description="Timestamp when notification was queued for sending"
    )
    sent_at: datetime | None = Field(
        None, description="Timestamp when notification was successfully sent"
    )
    failed_at: datetime | None = Field(
        None, description="Timestamp when the notification failed"
    )
    metadata: dict[str, Any] | None = Field(
        None, description="Additional metadata associated with notification"
    )
    recipient_id: UUID | None = Field(
        None, description="Unique identifier for the recipient user"
    )
