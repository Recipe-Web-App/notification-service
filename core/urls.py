"""URL routing configuration for core application."""

from django.urls import path

from .views import (
    HealthCheckView,
    LivenessCheckView,
    MentionView,
    NewFollowerView,
    NotificationDetailView,
    NotificationStatsView,
    PasswordResetView,
    ReadinessCheckView,
    RecipeCommentedView,
    RecipeLikedView,
    RecipePublishedView,
    UserNotificationListView,
    UserNotificationsByIdView,
)

urlpatterns = [
    # Health check endpoints
    path("health/", HealthCheckView.as_view(), name="health-check"),
    path("health/live", LivenessCheckView.as_view(), name="health-live"),
    path("health/ready", ReadinessCheckView.as_view(), name="health-ready"),
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
    # Admin endpoints (must come before notifications/<notification_id>)
    path(
        "notifications/stats",
        NotificationStatsView.as_view(),
        name="notification-stats",
    ),
    # Notification management endpoints
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
