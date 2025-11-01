"""Request schema for new follower notifications."""

from uuid import UUID

from pydantic import BaseModel, Field


class NewFollowerRequest(BaseModel):
    """Request schema for notifying users about new followers.

    Attributes:
        recipient_ids: List of recipient user IDs (users being followed).
                      Must contain at least 1 and at most 100 items.
        follower_id: UUID of the user who started following.
    """

    recipient_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of recipient user IDs (max 100)",
    )
    follower_id: UUID = Field(..., description="UUID of the user who started following")

    model_config = {
        "json_schema_extra": {
            "example": {
                "recipient_ids": ["550e8400-e29b-41d4-a716-446655440001"],
                "follower_id": "550e8400-e29b-41d4-a716-446655440002",
            }
        }
    }
