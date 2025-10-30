"""Schema for recipe published notification request."""

from uuid import UUID

from pydantic import BaseModel, Field


class RecipePublishedRequest(BaseModel):
    """Request schema for recipe published notifications."""

    recipient_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of recipient user IDs (max 100)",
    )
    recipe_id: UUID = Field(
        ...,
        description=(
            "UUID of the published recipe. Service will fetch recipe "
            "details from recipe-management-service."
        ),
    )
