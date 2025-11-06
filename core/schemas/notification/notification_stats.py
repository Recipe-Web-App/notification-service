"""Schema for notification statistics."""

from pydantic import BaseModel, Field


class StatusBreakdown(BaseModel):
    """Breakdown of notifications by status."""

    pending: int = Field(..., description="Number of pending notifications")
    queued: int = Field(..., description="Number of queued notifications")
    sent: int = Field(..., description="Number of sent notifications")
    failed: int = Field(..., description="Number of failed notifications")


class FailedNotificationsBreakdown(BaseModel):
    """Breakdown of failed notifications."""

    total: int = Field(..., description="Total number of failed notifications")
    by_error_type: dict[str, int] = Field(
        ..., description="Count of failures by error type"
    )


class DateRange(BaseModel):
    """Date range for statistics."""

    start: str | None = Field(
        None, description="Start date in ISO 8601 format (or null if no data)"
    )
    end: str | None = Field(
        None, description="End date in ISO 8601 format (or null if no data)"
    )


class NotificationStats(BaseModel):
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
    date_range: DateRange = Field(
        ..., description="Date range covered by these statistics"
    )
