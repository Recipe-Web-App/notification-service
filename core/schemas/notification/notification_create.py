"""Schema for creating notifications."""

from typing import Any
from uuid import UUID

from pydantic import EmailStr, Field

from core.schemas.base_schema_model import BaseSchemaModel


class NotificationCreate(BaseSchemaModel):
    """Schema for creating a new notification."""

    recipient_email: EmailStr = Field(..., description="Email address for delivery")
    subject: str = Field(
        ..., min_length=1, max_length=255, description="Email subject line"
    )
    message: str = Field(
        ..., min_length=1, description="HTML or plain text message content"
    )
    recipient_id: UUID | None = Field(None, description="Optional user ID")
    notification_type: str = Field(
        default="email", description="Type of notification (email, in_app, push, sms)"
    )
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")
    auto_queue: bool = Field(
        default=True, description="Automatically queue for sending"
    )
