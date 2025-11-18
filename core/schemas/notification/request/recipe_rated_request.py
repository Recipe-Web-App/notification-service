"""Schema for recipe rated notification request."""

from uuid import UUID

from pydantic import ConfigDict, Field

from core.schemas.base_schema_model import BaseSchemaModel


class RecipeRatedRequest(BaseSchemaModel):
    """Request schema for recipe rated notifications.

    Attributes:
        recipient_ids: List of recipient user IDs (typically the recipe author).
                      Must contain at least 1 and at most 100 items.
        recipe_id: ID of the rated recipe.
        rater_id: UUID of the user who rated the recipe.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recipient_ids": ["550e8400-e29b-41d4-a716-446655440001"],
                "recipe_id": 123,
                "rater_id": "550e8400-e29b-41d4-a716-446655440002",
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
            "ID of the rated recipe. Service will fetch recipe details and "
            "rating information from the database."
        ),
    )
    rater_id: UUID = Field(
        ...,
        description=(
            "UUID of the user who rated the recipe. Service will fetch rater "
            "details from user-management-service."
        ),
    )
