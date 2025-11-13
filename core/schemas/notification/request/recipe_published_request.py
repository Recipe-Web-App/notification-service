"""Schema for recipe published notification request."""

from uuid import UUID

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel


class RecipePublishedRequest(BaseSchemaModel):
    """Request schema for recipe published notifications."""

    recipient_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of recipient user IDs (max 100)",
    )
    recipe_id: int = Field(
        ...,
        description=(
            "ID of the published recipe. Service will fetch recipe "
            "details from recipe-management-service."
        ),
    )
