"""Schema for batch notification response."""

from uuid import UUID

from pydantic import BaseModel, Field


class NotificationCreated(BaseModel):
    """Schema for individual notification in batch response."""

    notification_id: UUID = Field(..., description="UUID of the created notification")
    recipient_id: UUID = Field(..., description="UUID of the recipient user")


class BatchNotificationResponse(BaseModel):
    """Response schema for batch notification requests."""

    notifications: list[NotificationCreated] = Field(
        ..., description="List of created notifications mapped to recipients"
    )
    queued_count: int = Field(
        ..., description="Number of notifications successfully queued"
    )
    message: str = Field(..., description="Success message")
