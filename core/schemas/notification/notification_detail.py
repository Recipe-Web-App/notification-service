"""Schema for notification details with delivery statuses."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel
from core.schemas.notification.notification_delivery_status import (
    NotificationDeliveryStatus,
)


class NotificationDetail(BaseSchemaModel):
    """Schema for detailed notification information including delivery statuses.

    The title and message fields are computed on-the-fly from
    notification_category + notification_data. They are not stored in
    the database.

    The delivery_statuses array shows the delivery status for each
    channel (EMAIL, IN_APP, PUSH, SMS). A single notification can have
    multiple delivery statuses if it was sent via multiple channels.
    """

    notification_id: UUID = Field(
        ..., description="Unique identifier for the notification"
    )
    user_id: UUID = Field(..., description="Owner of this notification")
    notification_category: str = Field(
        ...,
        description="Category determining template and notification_data structure",
    )
    is_read: bool = Field(
        ..., description="Whether the notification has been read (in-app state)"
    )
    is_deleted: bool = Field(
        ..., description="Whether the notification has been soft deleted"
    )
    created_at: datetime = Field(..., description="When the notification was created")
    updated_at: datetime = Field(
        ..., description="When the notification was last updated"
    )
    notification_data: dict[str, Any] = Field(
        ...,
        description="Template parameters including templateVersion for rendering",
    )
    title: str = Field(
        ...,
        description="Computed from category + notificationData (not stored)",
    )
    message: str | None = Field(
        None,
        description="Computed from category + notificationData (not stored)",
    )
    delivery_statuses: list[NotificationDeliveryStatus] = Field(
        ...,
        description="Delivery status for each channel (EMAIL, IN_APP, PUSH, SMS)",
    )
