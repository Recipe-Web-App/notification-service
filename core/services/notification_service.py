"""Notification service for managing email notifications."""

from typing import Any
from uuid import UUID

from django.db.models import QuerySet

import django_rq
import structlog

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


# Singleton instance
notification_service = NotificationService()
