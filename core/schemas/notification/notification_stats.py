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


class RetryStatistics(BaseModel):
    """Retry statistics for notifications."""

    total_retried: int = Field(
        ...,
        description=(
            "Total number of notifications that have been retried (retry_count > 0)"
        ),
    )
    currently_retrying: int = Field(
        ..., description="Number of FAILED notifications that can still be retried"
    )
    exhausted_retries: int = Field(
        ..., description="Number of FAILED notifications that have exhausted retries"
    )
    average_retries_before_success: float = Field(
        ..., description="Average retry_count for successfully sent notifications"
    )
    retry_success_rate: float = Field(
        ...,
        description=(
            "Success rate for retried notifications (sent with retries / total retried)"
        ),
        ge=0.0,
        le=1.0,
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
    retry_statistics: RetryStatistics = Field(
        ..., description="Statistics about notification retries"
    )
    date_range: DateRange = Field(
        ..., description="Date range covered by these statistics"
    )
