"""Schema for recipe featured notification request."""

from uuid import UUID

from pydantic import ConfigDict, Field

from core.schemas.base_schema_model import BaseSchemaModel


class RecipeFeaturedRequest(BaseSchemaModel):
    """Request schema for recipe featured notifications.

    Attributes:
        recipient_ids: List of recipient user IDs (recipe authors being notified).
                      Must contain at least 1 and at most 100 items.
        recipe_id: ID of the featured recipe.
        featured_reason: Optional reason or category for featuring the recipe.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recipient_ids": ["550e8400-e29b-41d4-a716-446655440001"],
                "recipe_id": 123,
                "featured_reason": "Editor's Choice - Outstanding presentation",
            }
        }
    )

    recipient_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description=(
            "List of recipient user IDs (recipe authors being notified "
            "their recipe is featured)"
        ),
    )
    recipe_id: int = Field(
        ...,
        description=(
            "ID of the featured recipe. Service will fetch recipe details "
            "from recipe-management-service."
        ),
    )
    featured_reason: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Optional reason or category for featuring (e.g., 'Editor's Choice', "
            "'Top Rated', 'Seasonal Favorite')"
        ),
    )
