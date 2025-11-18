"""Schema for recipe collected notification request."""

from uuid import UUID

from pydantic import ConfigDict, Field

from core.schemas.base_schema_model import BaseSchemaModel


class RecipeCollectedRequest(BaseSchemaModel):
    """Request schema for recipe collected notifications.

    Attributes:
        recipient_ids: List of recipient user IDs (typically the recipe author).
                      Must contain at least 1 and at most 100 items.
        recipe_id: ID of the recipe added to collection.
        collector_id: UUID of the user who added the recipe to their collection.
        collection_id: ID of the collection.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "recipient_ids": ["550e8400-e29b-41d4-a716-446655440001"],
                "recipe_id": 123,
                "collector_id": "550e8400-e29b-41d4-a716-446655440002",
                "collection_id": 456,
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
            "ID of the recipe added to collection. Service will fetch recipe "
            "details from recipe-management-service."
        ),
    )
    collector_id: UUID = Field(
        ...,
        description=(
            "UUID of the user who added the recipe to their collection. "
            "Service will fetch collector details from user-management-service."
        ),
    )
    collection_id: int = Field(
        ...,
        description=(
            "ID of the collection. Service will fetch collection details from "
            "recipe-management-service. Notification includes links to collection "
            "and collector profile."
        ),
    )
