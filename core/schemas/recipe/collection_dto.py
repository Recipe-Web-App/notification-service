"""Collection DTO schema from recipe-management service."""

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from core.schemas.base_schema_model import BaseSchemaModel


class CollectionDto(BaseSchemaModel):
    """Collection data transfer object from recipe-management service.

    This schema matches the GET /collections/{collectionId} response.
    Includes required fields and commonly used optional fields.
    """

    # Required fields
    collection_id: int = Field(
        ..., alias="collectionId", description="Unique collection identifier"
    )
    user_id: UUID = Field(
        ...,
        alias="userId",
        description="UUID of the user who created the collection",
    )
    name: str = Field(..., min_length=1, max_length=200, description="Collection name")
    created_at: datetime = Field(
        ..., alias="createdAt", description="Creation timestamp"
    )

    # Optional fields
    description: str | None = Field(
        None, max_length=1000, description="Collection description"
    )
    updated_at: datetime | None = Field(
        None, alias="updatedAt", description="Last update timestamp"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name is not empty after stripping."""
        if not v.strip():
            raise ValueError("Name cannot be empty or whitespace only")
        return v
