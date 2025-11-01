"""URL routing configuration for core application."""

from django.urls import path

from .views import (
    HealthCheckView,
    LivenessCheckView,
    MentionView,
    NewFollowerView,
    ReadinessCheckView,
    RecipeCommentedView,
    RecipeLikedView,
    RecipePublishedView,
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
]
