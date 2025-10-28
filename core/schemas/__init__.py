"""Schemas for the core app."""

from core.schemas.health import (
    DependencyHealth,
    LivenessResponse,
    ReadinessResponse,
)
from core.schemas.notification import (
    NotificationCreate,
    NotificationDetail,
    NotificationList,
    NotificationStats,
)
from core.schemas.user import UserBase, UserDetail

__all__ = [
    "DependencyHealth",
    "LivenessResponse",
    "NotificationCreate",
    "NotificationDetail",
    "NotificationList",
    "NotificationStats",
    "ReadinessResponse",
    "UserBase",
    "UserDetail",
]
