"""Readiness response schema."""

from pydantic import BaseModel, Field

from core.schemas.health.dependency_health import DependencyHealth


class ReadinessResponse(BaseModel):
    """Response model for readiness checks."""

    ready: bool = Field(..., description="Service is ready to serve requests")
    status: str = Field(
        ..., description="Overall status: 'ready', 'degraded', or 'not ready'"
    )
    degraded: bool = Field(
        ..., description="Whether service is running in degraded mode"
    )
    dependencies: dict[str, DependencyHealth] = Field(
        ..., description="Status of each dependency"
    )
