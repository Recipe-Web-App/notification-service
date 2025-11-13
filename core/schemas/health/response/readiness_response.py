"""Readiness response schema."""

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel
from core.schemas.health.dependency_health import DependencyHealth


class ReadinessResponse(BaseSchemaModel):
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
