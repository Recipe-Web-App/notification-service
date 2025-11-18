"""Request schema for password change notifications."""

from uuid import UUID

from pydantic import ConfigDict, Field

from core.schemas.base_schema_model import BaseSchemaModel


class PasswordChangedRequest(BaseSchemaModel):
    """Request schema for notifying users about password changes.

    Sends security notifications when a user's password is changed.
    Supports batch operations for multiple users.

    Attributes:
        recipient_ids: List of recipient user IDs (users whose password changed).
                      Must contain 1-100 items.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recipient_ids": ["550e8400-e29b-41d4-a716-446655440001"],
            }
        }
    )

    recipient_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of recipient user IDs (users whose password changed)",
    )
