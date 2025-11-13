"""Retry statistics schema for notifications."""

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel


class RetryStatistics(BaseSchemaModel):
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
