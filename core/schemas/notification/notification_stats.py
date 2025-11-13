"""Schema for notification statistics."""

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel
from core.schemas.notification.date_range import DateRange
from core.schemas.notification.failed_notifications_breakdown import (
    FailedNotificationsBreakdown,
)
from core.schemas.notification.retry_statistics import RetryStatistics
from core.schemas.notification.status_breakdown import StatusBreakdown


class NotificationStats(BaseSchemaModel):
    """Schema for comprehensive notification statistics.

    Matches the OpenAPI specification for GET /notifications/stats endpoint.
    """

    total_notifications: int = Field(..., description="Total number of notifications")
    status_breakdown: StatusBreakdown = Field(
        ..., description="Breakdown by notification status"
    )
    type_breakdown: dict[str, int] = Field(
        ..., description="Breakdown by notification type"
    )
    success_rate: float = Field(
        ..., description="Success rate (sent / total)", ge=0.0, le=1.0
    )
    average_send_time_seconds: float = Field(
        ..., description="Average time from queued to sent in seconds", ge=0.0
    )
    failed_notifications: FailedNotificationsBreakdown = Field(
        ..., description="Breakdown of failed notifications"
    )
    retry_statistics: RetryStatistics = Field(
        ..., description="Statistics about notification retries"
    )
    date_range: DateRange = Field(
        ..., description="Date range covered by these statistics"
    )
