"""Request schema for email change notifications."""

from uuid import UUID

from pydantic import ConfigDict, EmailStr, Field

from core.schemas.base_schema_model import BaseSchemaModel


class EmailChangedRequest(BaseSchemaModel):
    """Request schema for notifying users about email address changes.

    Sends security notifications to both old and new email addresses.

    Attributes:
        recipient_ids: Single recipient user ID (user whose email changed).
                      Must contain exactly 1 item.
        old_email: Previous email address (receives security alert).
        new_email: New email address (receives confirmation).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recipient_ids": ["550e8400-e29b-41d4-a716-446655440001"],
                "old_email": "old.email@example.com",
                "new_email": "new.email@example.com",
            }
        }
    )

    recipient_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=1,
        description="Single recipient (user whose email changed)",
    )
    old_email: EmailStr = Field(
        ...,
        description=(
            "Previous email address (notification sent here as security measure)"
        ),
    )
    new_email: EmailStr = Field(
        ...,
        description=("New email address (notification sent here for confirmation)"),
    )
