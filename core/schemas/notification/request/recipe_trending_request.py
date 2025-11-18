"""Schema for recipe trending notification request."""

from uuid import UUID

from pydantic import ConfigDict, Field

from core.schemas.base_schema_model import BaseSchemaModel


class RecipeTrendingRequest(BaseSchemaModel):
    """Request schema for recipe trending notifications.

    Attributes:
        recipient_ids: List of recipient user IDs (recipe authors being notified).
                      Must contain at least 1 and at most 100 items.
        recipe_id: ID of the trending recipe.
        trending_metrics: Optional trending metrics summary.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recipient_ids": ["550e8400-e29b-41d4-a716-446655440001"],
                "recipe_id": 123,
                "trending_metrics": "1,234 views and 89 likes in the past 24 hours",
            }
        }
    )

    recipient_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description=(
            "List of recipient user IDs (recipe authors being notified "
            "their recipe is trending)"
        ),
    )
    recipe_id: int = Field(
        ...,
        description=(
            "ID of the trending recipe. Service will fetch recipe details "
            "from recipe-management-service."
        ),
    )
    trending_metrics: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Optional trending metrics summary (e.g., '1,234 views and 89 likes "
            "in the past 24 hours')"
        ),
    )
