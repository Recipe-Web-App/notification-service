"""Liveness response schema."""

from pydantic import BaseModel, Field


class LivenessResponse(BaseModel):
    """Response model for liveness checks."""

    status: str = Field(..., description="Liveness status")
