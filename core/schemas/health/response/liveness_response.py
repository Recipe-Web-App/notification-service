"""Liveness response schema."""

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel


class LivenessResponse(BaseSchemaModel):
    """Response model for liveness checks."""

    status: str = Field(..., description="Liveness status")
