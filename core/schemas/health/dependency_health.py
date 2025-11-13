"""Dependency health schema."""

from pydantic import Field

from core.enums.health_status import HealthStatus
from core.schemas.base_schema_model import BaseSchemaModel


class DependencyHealth(BaseSchemaModel):
    """Health status for a single dependency."""

    healthy: bool = Field(..., description="Whether the dependency is healthy")
    status: HealthStatus = Field(..., description="Health status of the dependency")
    message: str = Field(..., description="Human-readable health message")
    response_time_ms: float | None = Field(
        None, description="Response time in milliseconds"
    )
