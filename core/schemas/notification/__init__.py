"""Notification schemas."""

from core.schemas.notification.batch_notification_response import (
    BatchNotificationResponse,
    NotificationCreated,
)
from core.schemas.notification.notification_create import NotificationCreate
from core.schemas.notification.notification_detail import NotificationDetail
from core.schemas.notification.notification_list import NotificationList
from core.schemas.notification.notification_stats import NotificationStats
from core.schemas.notification.recipe_liked_request import RecipeLikedRequest
from core.schemas.notification.recipe_published_request import (
    RecipePublishedRequest,
)

__all__ = [
    "BatchNotificationResponse",
    "NotificationCreate",
    "NotificationCreated",
    "NotificationDetail",
    "NotificationList",
    "NotificationStats",
    "RecipeLikedRequest",
    "RecipePublishedRequest",
]
