"""Schema for a user notification."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel


class UserNotification(BaseSchemaModel):
    """Schema for a user notification.

    Title and message are computed fields rendered from notification_category
    and notification_data by the service layer.
    """

    notification_id: UUID = Field(..., description="Unique notification identifier")
    user_id: UUID = Field(
        ..., description="ID of the user who received the notification"
    )
    notification_category: str = Field(
        ..., description="Category that determines the template"
    )
    is_read: bool = Field(..., description="Whether the notification has been read")
    is_deleted: bool = Field(..., description="Soft delete flag")
    created_at: datetime = Field(..., description="When the notification was created")
    updated_at: datetime = Field(
        ..., description="When the notification was last updated"
    )
    notification_data: dict[str, Any] = Field(
        ..., description="Template parameters and context data"
    )
    title: str = Field(..., description="Rendered notification title")
    message: str = Field(..., description="Rendered notification message")
