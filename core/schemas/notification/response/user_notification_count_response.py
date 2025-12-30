"""Schema for user notification count response."""

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel


class UserNotificationCountResponse(BaseSchemaModel):
    """Count-only response for notification queries.

    Returned by GET /notifications when countOnly=true.
    """

    total_count: int = Field(..., ge=0, description="Total number of notifications")
