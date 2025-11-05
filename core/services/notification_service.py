"""Notification service for managing email notifications."""

from typing import Any
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.http import Http404

import django_rq
import structlog

from core.auth.context import require_current_user
from core.exceptions.downstream_exceptions import ConflictError
from core.models.notification import Notification
from core.models.user import User

logger = structlog.get_logger(__name__)


class NotificationService:
    """Service for managing notifications and email queue.

    Provides high-level API for creating, queuing, and managing notifications.
    Integrates with Django-RQ for reliable async email delivery.
    """

    def __init__(self) -> None:
        """Initialize notification service."""
        self.queue = django_rq.get_queue("default")

    def create_notification(
        self,
        recipient_email: str,
        subject: str,
        message: str,
        recipient: User | None = None,
        notification_type: str = Notification.EMAIL,
        metadata: dict[str, Any] | None = None,
        auto_queue: bool = True,
    ) -> Notification:
        """Create a new notification.

        Args:
            recipient_email: Email address for delivery
            subject: Email subject line
            message: HTML or plain text message content
            recipient: Optional User instance
            notification_type: Type of notification (default: EMAIL)
            metadata: Additional metadata
            auto_queue: Automatically queue for sending (default: True)

        Returns:
            Created Notification instance
        """
        # Create notification
        notification = Notification.objects.create(
            recipient=recipient,
            recipient_email=recipient_email,
            subject=subject,
            message=message,
            notification_type=notification_type,
            metadata=metadata,
        )

        logger.info(
            "notification_created",
            notification_id=str(notification.notification_id),
            recipient_email=recipient_email,
            notification_type=notification_type,
        )

        # Queue for sending if auto_queue is True
        if auto_queue:
            self.queue_notification(notification.notification_id)

        return notification

    def queue_notification(self, notification_id: UUID) -> None:
        """Queue a notification for async sending.

        Args:
            notification_id: ID of notification to queue
        """
        # Import here to avoid circular dependency
        notification = Notification.objects.get(notification_id=notification_id)

        # Only queue if not already sent or queued
        if notification.status in [Notification.SENT, Notification.QUEUED]:
            logger.warning(
                "notification_already_processed",
                notification_id=str(notification_id),
                status=notification.status,
            )
            return

        # Queue the notification
        self.queue.enqueue(
            "core.jobs.email_jobs.send_email_job",
            str(notification_id),
        )

        # Update status
        notification.mark_queued()

        logger.info(
            "notification_queued",
            notification_id=str(notification_id),
        )

    def get_notification(self, notification_id: UUID) -> Notification:
        """Get a notification by ID.

        Args:
            notification_id: Notification ID

        Returns:
            Notification instance

        Raises:
            Notification.DoesNotExist: If notification not found
        """
        return Notification.objects.get(notification_id=notification_id)

    def get_user_notifications(
        self,
        user: User,
        status: str | None = None,
        notification_type: str | None = None,
        limit: int = 100,
    ) -> QuerySet[Notification]:
        """Get notifications for a user.

        Args:
            user: User instance
            status: Filter by status (optional)
            notification_type: Filter by type (optional)
            limit: Maximum number of results

        Returns:
            QuerySet of Notification instances
        """
        queryset = Notification.objects.filter(recipient=user)

        if status:
            queryset = queryset.filter(status=status)

        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        return queryset[:limit]

    def get_notifications_by_email(
        self,
        email: str,
        status: str | None = None,
        notification_type: str | None = None,
        limit: int = 100,
    ) -> QuerySet[Notification]:
        """Get notifications by email address.

        Args:
            email: Email address
            status: Filter by status (optional)
            notification_type: Filter by type (optional)
            limit: Maximum number of results

        Returns:
            QuerySet of Notification instances
        """
        queryset = Notification.objects.filter(recipient_email=email)

        if status:
            queryset = queryset.filter(status=status)

        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        return queryset[:limit]

    def retry_failed_notifications(self, max_retries: int = 3) -> int:
        """Retry failed notifications that haven't exceeded max retries.

        Args:
            max_retries: Maximum number of retry attempts

        Returns:
            Number of notifications requeued
        """
        # Find failed notifications that can be retried
        failed_notifications = Notification.objects.filter(
            status=Notification.FAILED,
            retry_count__lt=max_retries,
        )

        count = 0
        for notification in failed_notifications:
            if notification.can_retry():
                # Reset status to pending
                notification.status = Notification.PENDING
                notification.error_message = ""
                notification.save(update_fields=["status", "error_message"])

                # Requeue
                self.queue_notification(notification.notification_id)
                count += 1

        logger.info(
            "notifications_requeued",
            count=count,
        )

        return count

    def get_pending_notifications(self, limit: int = 100) -> QuerySet[Notification]:
        """Get pending notifications that need to be queued.

        Args:
            limit: Maximum number of results

        Returns:
            QuerySet of Notification instances
        """
        return Notification.objects.filter(status=Notification.PENDING)[:limit]

    def get_notification_stats(self) -> dict[str, int]:
        """Get notification statistics.

        Returns:
            Dictionary with counts by status
        """
        stats = {
            "total": Notification.objects.count(),
            "pending": Notification.objects.filter(status=Notification.PENDING).count(),
            "queued": Notification.objects.filter(status=Notification.QUEUED).count(),
            "sent": Notification.objects.filter(status=Notification.SENT).count(),
            "failed": Notification.objects.filter(status=Notification.FAILED).count(),
        }

        return stats

    def get_my_notifications(
        self,
        status: str | None = None,
        notification_type: str | None = None,
    ) -> QuerySet[Notification]:
        """Get notifications for the authenticated user.

        This method uses the security context to retrieve the current user
        and returns their notifications. Authorization is enforced - users
        can only see their own notifications unless they have admin scope.

        Args:
            status: Filter by status (optional)
            notification_type: Filter by type (optional)

        Returns:
            QuerySet of Notification instances ordered by created_at DESC

        Raises:
            PermissionDenied: If user is not authenticated
        """
        # Get current user from security context
        current_user = require_current_user()

        # Check user has required scope
        has_user_scope = current_user.has_scope("notification:user")
        has_admin_scope = current_user.has_scope("notification:admin")

        if not has_user_scope and not has_admin_scope:
            logger.warning(
                "insufficient_scope_for_notifications",
                user_id=current_user.user_id,
                scopes=current_user.scopes,
            )
            raise PermissionDenied(
                "Requires notification:user or notification:admin scope"
            )

        # Query by recipient_email since recipient FK is not populated in production
        # We use email from the OAuth2 token which is stored in current_user
        # Note: OAuth2User doesn't have an email attribute, we need to query by user_id
        # However, since recipient FK isn't populated, we need to use another approach
        # For now, we'll filter by recipient_email matching the user's email
        # This requires fetching the user's email from the token or user service

        # Since OAuth2User only has user_id, we need to get the email
        # The most reliable way is to query by recipient_email
        # But we need the email address from somewhere
        # Looking at the token structure, we should have email in the token
        # For now, let's use a query that works with the current data model

        # Filter by recipient user_id if recipient FK is set, or by email
        queryset = Notification.objects.filter(recipient_email__isnull=False)

        # Since we don't have a direct way to get the email from OAuth2User,
        # we'll need to enhance this. For now, let's use recipient__user_id
        # Actually, looking at the get_notification_for_user method, it uses recipient
        # Let's follow the same pattern but query for all notifications

        # The issue is that recipient FK is not populated in production
        # So we need to query by recipient_email
        # We'll need to get the user's email somehow
        # Let's check if we can get it from the User model using user_id

        try:
            # Try to get user by user_id to fetch their email
            user = User.objects.get(user_id=current_user.user_id)
            queryset = Notification.objects.filter(recipient_email=user.email)
        except User.DoesNotExist:
            # If user not found in local DB, return empty queryset
            # This shouldn't happen in normal flow
            logger.warning(
                "user_not_found_for_notifications",
                user_id=current_user.user_id,
            )
            queryset = Notification.objects.none()

        # Apply filters
        if status:
            queryset = queryset.filter(status=status)

        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        logger.info(
            "user_notifications_queried",
            user_id=current_user.user_id,
            status_filter=status,
            type_filter=notification_type,
        )

        # Return queryset ordered by created_at DESC - pagination handled by view
        return queryset.order_by("-created_at")

    def get_notification_for_user(
        self, notification_id: UUID, include_message: bool = False
    ) -> Notification:
        """Get a notification for the authenticated user with authorization check.

        Args:
            notification_id: Notification ID
            include_message: Whether to include the message body in the response

        Returns:
            Notification instance

        Raises:
            Http404: If notification not found
            PermissionDenied: If user is not authorized to view this notification
        """
        # Get current user from security context
        current_user = require_current_user()

        # Fetch notification
        try:
            notification = Notification.objects.get(notification_id=notification_id)
        except Notification.DoesNotExist as e:
            logger.warning(
                "notification_not_found",
                notification_id=str(notification_id),
                user_id=current_user.user_id,
            )
            raise Http404(f"Notification with ID {notification_id} not found") from e

        # Authorization check
        has_admin_scope = current_user.has_scope("notification:admin")
        is_owner = (
            notification.recipient
            and str(notification.recipient.user_id) == current_user.user_id
        )

        if not has_admin_scope and not is_owner:
            logger.warning(
                "unauthorized_notification_access",
                notification_id=str(notification_id),
                user_id=current_user.user_id,
                recipient_id=str(notification.recipient.user_id)
                if notification.recipient
                else None,
            )
            raise PermissionDenied("You can only view your own notifications")

        logger.info(
            "notification_retrieved",
            notification_id=str(notification_id),
            user_id=current_user.user_id,
            include_message=include_message,
        )

        return notification

    def delete_notification(self, notification_id: UUID) -> None:
        """Delete a notification with authorization and status checks.

        Args:
            notification_id: Notification ID

        Raises:
            Http404: If notification not found
            PermissionDenied: If user is not authorized to delete this notification
            ConflictError: If notification is in 'queued' status
        """
        # Get current user from security context
        current_user = require_current_user()

        # Fetch notification
        try:
            notification = Notification.objects.get(notification_id=notification_id)
        except Notification.DoesNotExist as e:
            logger.warning(
                "notification_not_found_for_deletion",
                notification_id=str(notification_id),
                user_id=current_user.user_id,
            )
            raise Http404(f"Notification with ID {notification_id} not found") from e

        # Authorization check
        has_admin_scope = current_user.has_scope("notification:admin")
        is_owner = (
            notification.recipient
            and str(notification.recipient.user_id) == current_user.user_id
        )

        if not has_admin_scope and not is_owner:
            logger.warning(
                "unauthorized_notification_deletion",
                notification_id=str(notification_id),
                user_id=current_user.user_id,
                recipient_id=str(notification.recipient.user_id)
                if notification.recipient
                else None,
            )
            raise PermissionDenied("You can only delete your own notifications")

        # Status check - cannot delete queued notifications
        if notification.status == Notification.QUEUED:
            logger.warning(
                "cannot_delete_queued_notification",
                notification_id=str(notification_id),
                user_id=current_user.user_id,
                status=notification.status,
            )
            raise ConflictError(
                "Cannot delete notification while it is being processed",
                detail=f"Notification status is '{notification.status}'",
            )

        # Delete the notification
        notification.delete()

        logger.info(
            "notification_deleted",
            notification_id=str(notification_id),
            user_id=current_user.user_id,
        )


# Singleton instance
notification_service = NotificationService()
