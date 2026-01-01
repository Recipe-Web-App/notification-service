"""Service for user-facing notification management.

This module provides the UserNotificationService class which handles
user-facing notification CRUD operations including fetching notifications,
marking as read, and soft-deleting notifications.
"""

from uuid import UUID

from django.http import Http404
from django.utils import timezone

import structlog

from core.auth.context import require_current_user
from core.models import Notification
from core.schemas.notification import (
    UserNotification,
    UserNotificationCountResponse,
    UserNotificationListResponse,
)

logger = structlog.get_logger(__name__)


# Template map for rendering title/message from category + data
NOTIFICATION_TEMPLATES: dict[str, dict[str, str]] = {
    # Recipe events
    "RECIPE_PUBLISHED": {
        "title": "Recipe Published",
        "message": "{actor_name} published a new recipe: {recipe_title}",
    },
    "RECIPE_LIKED": {
        "title": "Someone liked your recipe",
        "message": "{actor_name} liked {recipe_title}",
    },
    "RECIPE_COMMENTED": {
        "title": "New comment on your recipe",
        "message": "{actor_name} commented on {recipe_title}",
    },
    "RECIPE_SHARED": {
        "title": "Recipe shared with you",
        "message": "{actor_name} shared {recipe_title} with you",
    },
    "RECIPE_COLLECTED": {
        "title": "Recipe added to collection",
        "message": "{actor_name} added {recipe_title} to their collection",
    },
    "RECIPE_RATED": {
        "title": "Your recipe was rated",
        "message": "{actor_name} rated {recipe_title}",
    },
    "RECIPE_FEATURED": {
        "title": "Your recipe is featured!",
        "message": "{recipe_title} has been featured",
    },
    "RECIPE_TRENDING": {
        "title": "Your recipe is trending!",
        "message": "{recipe_title} is trending",
    },
    # Social events
    "NEW_FOLLOWER": {
        "title": "New follower",
        "message": "{actor_name} started following you",
    },
    "MENTION": {
        "title": "You were mentioned",
        "message": "{actor_name} mentioned you in a comment",
    },
    "COLLECTION_INVITE": {
        "title": "Collection invite",
        "message": "{actor_name} invited you to collaborate on {collection_name}",
    },
    # System events
    "WELCOME": {
        "title": "Welcome!",
        "message": "Welcome to the recipe app",
    },
    "PASSWORD_RESET": {
        "title": "Password Reset",
        "message": "Your password reset link is ready",
    },
    "PASSWORD_CHANGED": {
        "title": "Password Changed",
        "message": "Your password was successfully changed",
    },
    "EMAIL_CHANGED": {
        "title": "Email Changed",
        "message": "Your email address was updated",
    },
    "MAINTENANCE": {
        "title": "Scheduled Maintenance",
        "message": "Scheduled maintenance: {description}",
    },
    "SYSTEM_ALERT": {
        "title": "System Alert",
        "message": "{description}",
    },
}


class UserNotificationService:
    """Service for user-facing notification management.

    This service handles all user-facing notification operations including
    fetching notifications with pagination, marking notifications as read,
    and soft-deleting notifications.
    """

    def get_user_notifications(
        self,
        count_only: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> UserNotificationListResponse | UserNotificationCountResponse:
        """Get notifications for authenticated user.

        Args:
            count_only: If True, return only the count of notifications.
            limit: Maximum number of results to return (1-100).
            offset: Number of results to skip for pagination.

        Returns:
            UserNotificationListResponse with paginated notifications, or
            UserNotificationCountResponse with count only if count_only=True.

        Raises:
            PermissionDenied: If user is not authenticated.
        """
        current_user = require_current_user()
        logger.info(
            "get_user_notifications",
            user_id=str(current_user.user_id),
            count_only=count_only,
            limit=limit,
            offset=offset,
        )

        queryset = Notification.objects.filter(
            user_id=current_user.user_id,
            is_deleted=False,
        ).order_by("-created_at")

        total_count = queryset.count()

        if count_only:
            return UserNotificationCountResponse(total_count=total_count)

        # Apply pagination via slicing
        notifications = list(queryset[offset : offset + limit])
        rendered = [self._render_notification(n) for n in notifications]

        return UserNotificationListResponse(
            notifications=rendered,
            total_count=total_count,
            limit=limit,
            offset=offset,
        )

    def mark_as_read(self, notification_id: UUID) -> Notification:
        """Mark a single notification as read.

        Args:
            notification_id: UUID of the notification to mark as read.

        Returns:
            The updated Notification instance.

        Raises:
            Http404: If notification not found or doesn't belong to user.
            PermissionDenied: If user is not authenticated.
        """
        current_user = require_current_user()
        logger.info(
            "mark_notification_as_read",
            user_id=str(current_user.user_id),
            notification_id=str(notification_id),
        )

        try:
            notification = Notification.objects.get(
                notification_id=notification_id,
                user_id=current_user.user_id,
                is_deleted=False,
            )
        except Notification.DoesNotExist as err:
            logger.warning(
                "notification_not_found",
                notification_id=str(notification_id),
                user_id=str(current_user.user_id),
            )
            raise Http404("Notification not found") from err

        notification.is_read = True
        notification.save(update_fields=["is_read", "updated_at"])

        logger.info(
            "notification_marked_as_read",
            notification_id=str(notification_id),
        )
        return notification

    def mark_all_as_read(self) -> list[UUID]:
        """Mark all user's unread notifications as read.

        Returns:
            List of notification IDs that were marked as read.

        Raises:
            PermissionDenied: If user is not authenticated.
        """
        current_user = require_current_user()
        logger.info(
            "mark_all_notifications_as_read",
            user_id=str(current_user.user_id),
        )

        # Get IDs of unread notifications before updating
        unread_ids = list(
            Notification.objects.filter(
                user_id=current_user.user_id,
                is_deleted=False,
                is_read=False,
            ).values_list("notification_id", flat=True)
        )

        if unread_ids:
            Notification.objects.filter(
                notification_id__in=unread_ids,
            ).update(is_read=True, updated_at=timezone.now())

        logger.info(
            "all_notifications_marked_as_read",
            user_id=str(current_user.user_id),
            count=len(unread_ids),
        )
        return unread_ids

    def bulk_delete(self, notification_ids: list[UUID]) -> list[UUID]:
        """Soft delete multiple notifications.

        Args:
            notification_ids: List of notification IDs to delete (1-100).

        Returns:
            List of notification IDs that were actually deleted.

        Raises:
            PermissionDenied: If user is not authenticated.
        """
        current_user = require_current_user()
        logger.info(
            "bulk_delete_notifications",
            user_id=str(current_user.user_id),
            notification_count=len(notification_ids),
        )

        # Filter to only notifications owned by user and not already deleted
        owned_ids = list(
            Notification.objects.filter(
                notification_id__in=notification_ids,
                user_id=current_user.user_id,
                is_deleted=False,
            ).values_list("notification_id", flat=True)
        )

        if owned_ids:
            Notification.objects.filter(
                notification_id__in=owned_ids,
            ).update(is_deleted=True, updated_at=timezone.now())

        logger.info(
            "notifications_deleted",
            user_id=str(current_user.user_id),
            requested_count=len(notification_ids),
            deleted_count=len(owned_ids),
        )
        return owned_ids

    def _render_notification(self, notification: Notification) -> UserNotification:
        """Render a notification to response schema with computed title/message.

        Args:
            notification: The Notification model instance.

        Returns:
            UserNotification schema with title and message populated from
            the template map based on notification_category and notification_data.
        """
        template = NOTIFICATION_TEMPLATES.get(
            notification.notification_category,
            {"title": "Notification", "message": notification.notification_category},
        )

        # Safely interpolate template with notification_data
        data = notification.notification_data or {}
        try:
            title = template["title"].format(**data)
            message = template["message"].format(**data)
        except KeyError:
            # Fallback if data is missing expected keys
            title = template["title"]
            message = template["message"]

        return UserNotification(
            notification_id=notification.notification_id,
            user_id=notification.user_id,
            notification_category=notification.notification_category,
            is_read=notification.is_read,
            is_deleted=notification.is_deleted,
            created_at=notification.created_at,
            updated_at=notification.updated_at,
            notification_data=data,
            title=title,
            message=message,
        )


# Singleton instance for use throughout the application
user_notification_service = UserNotificationService()
