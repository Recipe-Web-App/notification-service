"""Schema for notification delivery status per channel."""

from datetime import datetime

from pydantic import EmailStr, Field

from core.schemas.base_schema_model import BaseSchemaModel


class NotificationDeliveryStatus(BaseSchemaModel):
    """Schema for per-channel delivery status tracking.

    Represents the delivery status for a specific channel (EMAIL, IN_APP,
    PUSH, SMS) for a notification.
    """

    notification_type: str = Field(
        ..., description="Delivery channel type (EMAIL, IN_APP, PUSH, SMS)"
    )
    status: str = Field(
        ..., description="Delivery status (PENDING, QUEUED, SENT, FAILED, ABORTED)"
    )
    retry_count: int | None = Field(
        None, description="Number of delivery attempts (null if no retries)"
    )
    error_message: str | None = Field(
        None, description="Error message if status is FAILED"
    )
    recipient_email: EmailStr | None = Field(
        None, description="Recipient email address (for EMAIL channel only)"
    )
    created_at: datetime = Field(..., description="When the status record was created")
    updated_at: datetime = Field(..., description="When the status was last updated")
    queued_at: datetime | None = Field(
        None, description="When the notification was queued for delivery"
    )
    sent_at: datetime | None = Field(
        None, description="When the notification was successfully sent"
    )
    failed_at: datetime | None = Field(
        None, description="When the notification permanently failed"
    )
