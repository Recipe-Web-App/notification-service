"""Schema for recipe shared notification request."""

from uuid import UUID

from pydantic import ConfigDict, Field

from core.schemas.base_schema_model import BaseSchemaModel


class RecipeSharedRequest(BaseSchemaModel):
    """Request schema for recipe shared notifications.

    Attributes:
        recipient_ids: List of recipient user IDs (typically the recipe author).
                      Must contain at least 1 and at most 100 items.
        recipe_id: ID of the shared recipe.
        sharer_id: Optional UUID of the user who shared the recipe.
        share_message: Optional message from the sharer about why they're sharing.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recipient_ids": ["550e8400-e29b-41d4-a716-446655440001"],
                "recipe_id": 123,
                "sharer_id": "550e8400-e29b-41d4-a716-446655440002",
                "share_message": "Check out this amazing recipe!",
            }
        }
    )

    recipient_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of recipient user IDs (typically the recipe author)",
    )
    recipe_id: int = Field(
        ...,
        description=(
            "ID of the shared recipe. Service will fetch recipe "
            "details from recipe-management-service."
        ),
    )
    sharer_id: UUID | None = Field(
        default=None,
        description=(
            "Optional UUID of the user who shared the recipe. "
            "Only included in notification if sharer has public profile "
            "or follows recipient. Service will fetch sharer details "
            "from user-management-service."
        ),
    )
    share_message: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Optional message from the sharer about why they're sharing the recipe"
        ),
    )
