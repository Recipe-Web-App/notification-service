"""Notification schemas."""

from core.schemas.notification.batch_notification_response import (
    BatchNotificationResponse,
    NotificationCreated,
)
from core.schemas.notification.mention_request import MentionRequest
from core.schemas.notification.new_follower_request import NewFollowerRequest
from core.schemas.notification.notification_create import NotificationCreate
from core.schemas.notification.notification_detail import NotificationDetail
from core.schemas.notification.notification_list import NotificationList
from core.schemas.notification.notification_list_response import (
    NotificationListResponse,
)
from core.schemas.notification.notification_stats import NotificationStats
from core.schemas.notification.password_reset_request import PasswordResetRequest
from core.schemas.notification.recipe_commented_request import (
    RecipeCommentedRequest,
)
from core.schemas.notification.recipe_liked_request import RecipeLikedRequest
from core.schemas.notification.recipe_published_request import (
    RecipePublishedRequest,
)
from core.schemas.notification.template_info import (
    TemplateInfo,
    TemplateListResponse,
)
from core.schemas.notification.welcome_request import WelcomeRequest

__all__ = [
    "BatchNotificationResponse",
    "MentionRequest",
    "NewFollowerRequest",
    "NotificationCreate",
    "NotificationCreated",
    "NotificationDetail",
    "NotificationList",
    "NotificationListResponse",
    "NotificationStats",
    "PasswordResetRequest",
    "RecipeCommentedRequest",
    "RecipeLikedRequest",
    "RecipePublishedRequest",
    "TemplateInfo",
    "TemplateListResponse",
    "WelcomeRequest",
]
