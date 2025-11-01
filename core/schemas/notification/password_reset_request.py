"""Request schema for password reset notifications."""

from uuid import UUID

from pydantic import BaseModel, Field


class PasswordResetRequest(BaseModel):
    """Request schema for notifying users about password reset.

    Attributes:
        recipient_ids: List of recipient user IDs (single user requesting reset).
                      Must contain exactly 1 item.
        reset_token: Secure reset token (minimum 20 characters).
        expiry_hours: Number of hours until token expires (1-72).
    """

    recipient_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=1,
        description="Single recipient (user requesting reset)",
    )
    reset_token: str = Field(
        ...,
        min_length=20,
        description="Secure reset token",
    )
    expiry_hours: int = Field(
        ...,
        ge=1,
        le=72,
        description="Number of hours until token expires",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "recipient_ids": ["550e8400-e29b-41d4-a716-446655440001"],
                "reset_token": "abc123def456ghi789jkl",
                "expiry_hours": 24,
            }
        }
    }
