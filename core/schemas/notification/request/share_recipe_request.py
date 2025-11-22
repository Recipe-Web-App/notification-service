"""Schema for share recipe request."""

from uuid import UUID

from pydantic import ConfigDict, Field

from core.schemas.base_schema_model import BaseSchemaModel


class ShareRecipeRequest(BaseSchemaModel):
    """Request schema for sharing a recipe with users.

    This endpoint shares a recipe with recipient users and sends notifications
    to both the recipients (with recipe preview) and the recipe author
    (privacy-aware notification about the share).

    Attributes:
        recipient_ids: List of user IDs to share the recipe with.
                      Must contain at least 1 and at most 100 items.
        recipe_id: ID of the recipe being shared.
        sharer_id: Optional UUID of the user sharing the recipe.
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
        description="List of user IDs to share the recipe with",
    )
    recipe_id: int = Field(
        ...,
        description=(
            "ID of the recipe being shared. Service will fetch recipe "
            "details from recipe-management-service."
        ),
    )
    sharer_id: UUID | None = Field(
        default=None,
        description=(
            "Optional UUID of the user sharing the recipe. "
            "Identity revealed to recipients (deliberate share). "
            "For recipe author notification, identity only revealed if sharer "
            "follows author or has admin scope. Service will fetch sharer details "
            "from user-management-service."
        ),
    )
    share_message: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Optional message from the sharer about why they're sharing the recipe. "
            "Shown to both recipients and recipe author."
        ),
    )
