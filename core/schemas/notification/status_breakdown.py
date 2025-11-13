"""Schema for breakdown of notifications by status."""

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel


class StatusBreakdown(BaseSchemaModel):
    """Breakdown of notifications by status."""

    pending: int = Field(..., description="Number of pending notifications")
    queued: int = Field(..., description="Number of queued notifications")
    sent: int = Field(..., description="Number of sent notifications")
    failed: int = Field(..., description="Number of failed notifications")
