"""Schema for recipe liked notification request."""

from uuid import UUID

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel


class RecipeLikedRequest(BaseSchemaModel):
    """Request schema for recipe liked notifications."""

    recipient_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of recipient user IDs (typically the recipe author)",
    )
    recipe_id: int = Field(
        ...,
        description=(
            "ID of the liked recipe. Service will fetch recipe "
            "details from recipe-management-service."
        ),
    )
    liker_id: UUID = Field(
        ...,
        description=(
            "UUID of the user who liked the recipe. Service will fetch "
            "user details from user-management-service."
        ),
    )
