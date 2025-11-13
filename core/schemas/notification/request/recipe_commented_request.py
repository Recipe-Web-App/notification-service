"""Schema for recipe commented notification request."""

from uuid import UUID

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel


class RecipeCommentedRequest(BaseSchemaModel):
    """Request schema for recipe commented notifications."""

    recipient_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of recipient user IDs (typically the recipe author)",
    )
    comment_id: int = Field(
        ...,
        description=(
            "ID of the comment. Service will fetch comment details "
            "(including recipe_id and commenter info) from recipe-management-service."
        ),
    )
