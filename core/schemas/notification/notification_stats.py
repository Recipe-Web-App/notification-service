"""Schema for notification statistics."""

from pydantic import BaseModel


class NotificationStats(BaseModel):
    """Schema for notification statistics."""

    total: int
    pending: int
    queued: int
    sent: int
    failed: int
