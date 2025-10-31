"""Comment DTO schema from recipe-management service."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CommentDto(BaseModel):
    """Comment data transfer object from recipe-management service.

    This schema matches the GET /comments/{commentId} response.
    Includes comment details needed for notifications.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=False,
    )

    # Required fields
    comment_id: UUID = Field(
        ..., alias="commentId", description="Unique comment identifier"
    )
    recipe_id: int = Field(
        ..., alias="recipeId", description="ID of the recipe being commented on"
    )
    user_id: UUID = Field(
        ..., alias="userId", description="UUID of the user who made the comment"
    )
    comment_text: str = Field(
        ..., alias="commentText", min_length=1, description="The comment content"
    )
    created_at: datetime = Field(
        ..., alias="createdAt", description="When the comment was created"
    )

    # Optional fields
    updated_at: datetime | None = Field(
        None, alias="updatedAt", description="Last update timestamp"
    )
    parent_comment_id: UUID | None = Field(
        None, alias="parentCommentId", description="Parent comment ID for replies"
    )
