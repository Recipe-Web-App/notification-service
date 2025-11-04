"""Schema for paginated notification list response."""

from pydantic import BaseModel, ConfigDict

from core.schemas.notification.notification_detail import NotificationDetail


class NotificationListResponse(BaseModel):
    """Schema for paginated list of notifications.

    This schema matches the OpenAPI specification for notification list endpoints,
    providing pagination metadata including next/previous page URLs.
    """

    model_config = ConfigDict(from_attributes=True)

    results: list[NotificationDetail]
    count: int
    next: str | None = None
    previous: str | None = None
