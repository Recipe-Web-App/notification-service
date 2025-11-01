"""Request schema for mention notifications."""

from uuid import UUID

from pydantic import BaseModel, Field


class MentionRequest(BaseModel):
    """Request schema for notifying users when mentioned in comments.

    Attributes:
        recipient_ids: List of recipient user IDs (users mentioned in comment).
                      Must contain at least 1 and at most 100 items.
        comment_id: UUID of the comment containing the mention.
    """

    recipient_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of recipient user IDs (max 100)",
    )
    comment_id: UUID = Field(
        ..., description="UUID of the comment containing the mention"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "recipient_ids": ["550e8400-e29b-41d4-a716-446655440001"],
                "comment_id": "880e8400-e29b-41d4-a716-446655440123",
            }
        }
    }
