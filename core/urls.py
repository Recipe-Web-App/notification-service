"""URL routing configuration for core application."""

from django.urls import path

from .views import (
    EmailChangedView,
    LivenessCheckView,
    MentionView,
    NewFollowerView,
    NotificationDetailView,
    NotificationRetryStatusView,
    NotificationStatsView,
    PasswordChangedView,
    PasswordResetView,
    ReadinessCheckView,
    RecipeCollectedView,
    RecipeCommentedView,
    RecipeFeaturedView,
    RecipeLikedView,
    RecipePublishedView,
    RecipeRatedView,
    RecipeSharedView,
    RecipeTrendingView,
    RetryFailedNotificationsView,
    RetryNotificationView,
    TemplateListView,
    UserNotificationListView,
    UserNotificationsByIdView,
    WelcomeView,
)

urlpatterns = [
    # Health check endpoints
    path("health/live", LivenessCheckView.as_view(), name="health-live"),
    path("health/ready", ReadinessCheckView.as_view(), name="health-ready"),
    # Template endpoints
    path("templates", TemplateListView.as_view(), name="template-list"),
    # Notification endpoints
    path(
        "notifications/recipe-published",
        RecipePublishedView.as_view(),
        name="recipe-published",
    ),
    path(
        "notifications/recipe-liked",
        RecipeLikedView.as_view(),
        name="recipe-liked",
    ),
    path(
        "notifications/recipe-commented",
        RecipeCommentedView.as_view(),
        name="recipe-commented",
    ),
    path(
        "notifications/recipe-shared",
        RecipeSharedView.as_view(),
        name="recipe-shared",
    ),
    path(
        "notifications/recipe-collected",
        RecipeCollectedView.as_view(),
        name="recipe-collected",
    ),
    path(
        "notifications/recipe-rated",
        RecipeRatedView.as_view(),
        name="recipe-rated",
    ),
    path(
        "notifications/recipe-featured",
        RecipeFeaturedView.as_view(),
        name="recipe-featured",
    ),
    path(
        "notifications/recipe-trending",
        RecipeTrendingView.as_view(),
        name="recipe-trending",
    ),
    path(
        "notifications/new-follower",
        NewFollowerView.as_view(),
        name="new-follower",
    ),
    path(
        "notifications/mention",
        MentionView.as_view(),
        name="mention",
    ),
    path(
        "notifications/password-reset",
        PasswordResetView.as_view(),
        name="password-reset",
    ),
    path(
        "notifications/welcome",
        WelcomeView.as_view(),
        name="welcome",
    ),
    path(
        "notifications/email-changed",
        EmailChangedView.as_view(),
        name="email-changed",
    ),
    path(
        "notifications/password-changed",
        PasswordChangedView.as_view(),
        name="password-changed",
    ),
    # Admin endpoints (must come before notifications/<notification_id>)
    path(
        "stats",
        NotificationStatsView.as_view(),
        name="notification-stats",
    ),
    path(
        "notifications/retry-failed",
        RetryFailedNotificationsView.as_view(),
        name="retry-failed-notifications",
    ),
    path(
        "notifications/retry-status",
        NotificationRetryStatusView.as_view(),
        name="notification-retry-status",
    ),
    # Notification management endpoints (specific routes before generic)
    path(
        "notifications/<str:notification_id>/retry",
        RetryNotificationView.as_view(),
        name="retry-notification",
    ),
    path(
        "notifications/<str:notification_id>",
        NotificationDetailView.as_view(),
        name="notification-detail",
    ),
    # User notification endpoints
    path(
        "users/me/notifications",
        UserNotificationListView.as_view(),
        name="user-notifications",
    ),
    path(
        "users/<str:user_id>/notifications",
        UserNotificationsByIdView.as_view(),
        name="user-notifications-by-id",
    ),
]
