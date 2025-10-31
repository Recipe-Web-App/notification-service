"""URL routing configuration for core application."""

from django.urls import path

from .views import (
    HealthCheckView,
    LivenessCheckView,
    ReadinessCheckView,
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
]
