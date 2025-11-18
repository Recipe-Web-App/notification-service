"""Notification schemas."""

from core.schemas.notification.notification_create import NotificationCreate
from core.schemas.notification.notification_created import NotificationCreated
from core.schemas.notification.notification_detail import NotificationDetail
from core.schemas.notification.notification_list import NotificationList
from core.schemas.notification.notification_stats import NotificationStats
from core.schemas.notification.request.mention_request import MentionRequest
from core.schemas.notification.request.new_follower_request import NewFollowerRequest
from core.schemas.notification.request.password_reset_request import (
    PasswordResetRequest,
)
from core.schemas.notification.request.recipe_collected_request import (
    RecipeCollectedRequest,
)
from core.schemas.notification.request.recipe_commented_request import (
    RecipeCommentedRequest,
)
from core.schemas.notification.request.recipe_featured_request import (
    RecipeFeaturedRequest,
)
from core.schemas.notification.request.recipe_liked_request import RecipeLikedRequest
from core.schemas.notification.request.recipe_published_request import (
    RecipePublishedRequest,
)
from core.schemas.notification.request.recipe_rated_request import RecipeRatedRequest
from core.schemas.notification.request.recipe_shared_request import (
    RecipeSharedRequest,
)
from core.schemas.notification.request.recipe_trending_request import (
    RecipeTrendingRequest,
)
from core.schemas.notification.request.welcome_request import WelcomeRequest
from core.schemas.notification.response.batch_notification_response import (
    BatchNotificationResponse,
)
from core.schemas.notification.response.notification_list_response import (
    NotificationListResponse,
)
from core.schemas.notification.response.template_list_response import (
    TemplateListResponse,
)
from core.schemas.notification.template_info import TemplateInfo

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
    "RecipeCollectedRequest",
    "RecipeCommentedRequest",
    "RecipeFeaturedRequest",
    "RecipeLikedRequest",
    "RecipePublishedRequest",
    "RecipeRatedRequest",
    "RecipeSharedRequest",
    "RecipeTrendingRequest",
    "TemplateInfo",
    "TemplateListResponse",
    "WelcomeRequest",
]
