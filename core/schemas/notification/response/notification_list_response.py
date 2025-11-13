"""Schema for paginated notification list response."""

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel
from core.schemas.notification.notification_detail import NotificationDetail


class NotificationListResponse(BaseSchemaModel):
    """Schema for paginated list of notifications.

    This schema matches the OpenAPI specification for notification list endpoints,
    providing pagination metadata including next/previous page URLs.
    """

    results: list[NotificationDetail] = Field(
        ..., description="List of notification details"
    )
    count: int = Field(..., ge=0, description="Total number of notifications")
    next: str | None = Field(None, description="URL for the next page of results")
    previous: str | None = Field(
        None, description="URL for the previous page of results"
    )
