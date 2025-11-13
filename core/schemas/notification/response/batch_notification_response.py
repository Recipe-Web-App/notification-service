"""Schema for batch notification response."""

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel
from core.schemas.notification.notification_created import NotificationCreated


class BatchNotificationResponse(BaseSchemaModel):
    """Response schema for batch notification requests."""

    notifications: list[NotificationCreated] = Field(
        ..., description="List of created notifications mapped to recipients"
    )
    queued_count: int = Field(
        ..., description="Number of notifications successfully queued"
    )
    message: str = Field(..., description="Success message")
