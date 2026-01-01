"""Schema for paginated user notification list response."""

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel
from core.schemas.notification.response.user_notification import UserNotification


class UserNotificationListResponse(BaseSchemaModel):
    """Paginated list of user notifications.

    Returned by GET /notifications when countOnly is false or not specified.
    """

    notifications: list[UserNotification] = Field(
        ..., description="List of notifications"
    )
    total_count: int = Field(
        ..., ge=0, description="Total number of notifications matching the query"
    )
    limit: int = Field(..., ge=1, description="Maximum number of results per page")
    offset: int = Field(..., ge=0, description="Number of results skipped")
