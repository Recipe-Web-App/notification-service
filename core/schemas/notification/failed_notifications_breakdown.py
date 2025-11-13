"""Schema for failed notifications breakdown."""

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel


class FailedNotificationsBreakdown(BaseSchemaModel):
    """Breakdown of failed notifications."""

    total: int = Field(..., description="Total number of failed notifications")
    by_error_type: dict[str, int] = Field(
        ..., description="Count of failures by error type"
    )
