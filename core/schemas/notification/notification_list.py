"""Schema for notification lists."""

from pydantic import BaseModel

from core.schemas.notification.notification_detail import NotificationDetail


class NotificationList(BaseModel):
    """Schema for list of notifications."""

    notifications: list[NotificationDetail]
    total: int
    page: int = 1
    page_size: int = 100
