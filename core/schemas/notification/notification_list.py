"""Schema for notification lists."""

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel
from core.schemas.notification.notification_detail import NotificationDetail


class NotificationList(BaseSchemaModel):
    """Schema for list of notifications."""

    notifications: list[NotificationDetail] = Field(
        ..., description="List of notification details"
    )
    total: int = Field(..., ge=0, description="Total number of notifications")
    page: int = Field(1, ge=1, description="Current page number")
    page_size: int = Field(100, ge=1, le=1000, description="Number of items per page")
