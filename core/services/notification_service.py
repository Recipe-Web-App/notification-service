"""Notification service for managing notifications with two-table design.

This module provides the NotificationService class which manages the creation,
queuing, and lifecycle of notifications using the normalized two-table design:
- Notification: User-facing notification data
- NotificationStatus: Per-channel delivery tracking (EMAIL, IN_APP, etc.)
"""

from typing import Any
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet
from django.http import Http404
from django.utils import timezone

import django_rq
import structlog

from core.auth.context import require_current_user
from core.enums.notification import NotificationType
from core.exceptions.downstream_exceptions import ConflictError, UserNotFoundError
from core.models import Notification, NotificationStatus, User

logger = structlog.get_logger(__name__)


class NotificationService:
    """Service for managing notifications and email queue.

    Provides high-level API for creating, queuing, and managing notifications.
    Uses the normalized two-table design:
    - Notification: User-facing notification data
    - NotificationStatus: Per-channel delivery tracking
    """

    def __init__(self) -> None:
        """Initialize notification service."""
        self.queue = django_rq.get_queue("default")

    def create_notification(
        self,
        user: User,
        notification_category: str,
        notification_data: dict[str, Any],
        recipient_email: str,
        auto_queue: bool = True,
    ) -> tuple[Notification, list[NotificationStatus]]:
        """Create a new notification with delivery status records.

        Creates a Notification record and NotificationStatus records for
        EMAIL and IN_APP channels. The IN_APP status is marked as SENT
        immediately since it doesn't require delivery.

        Args:
            user: User instance receiving the notification.
            notification_category: Category determining template rendering.
            notification_data: Template parameters (must include template_version).
            recipient_email: Email address for EMAIL delivery.
            auto_queue: Automatically queue EMAIL for sending (default: True).

        Returns:
            Tuple of (Notification, [NotificationStatus, ...]).
        """
        notification = Notification.objects.create(
            user=user,
            notification_category=notification_category,
            notification_data=notification_data,
            is_read=False,
            is_deleted=False,
        )

        email_status = NotificationStatus.objects.create(
            notification=notification,
            notification_type=NotificationType.EMAIL.value,
            status="PENDING",
            recipient_email=recipient_email,
        )

        in_app_status = NotificationStatus.objects.create(
            notification=notification,
            notification_type=NotificationType.IN_APP.value,
            status="SENT",
            sent_at=timezone.now(),
        )

        logger.info(
            "notification_created",
            notification_id=str(notification.notification_id),
            user_id=str(user.user_id),
            notification_category=notification_category,
            recipient_email=recipient_email,
        )

        if auto_queue:
            self.queue_notification(notification.notification_id)

        return notification, [email_status, in_app_status]

    def queue_notification(
        self,
        notification_id: UUID,
        notification_type: str = NotificationType.EMAIL.value,
    ) -> None:
        """Queue a notification channel for async sending.

        Args:
            notification_id: ID of notification to queue.
            notification_type: Channel to queue (default: EMAIL).
        """
        try:
            status = NotificationStatus.objects.get(
                notification_id=notification_id,
                notification_type=notification_type,
            )
        except NotificationStatus.DoesNotExist:
            logger.error(
                "notification_status_not_found",
                notification_id=str(notification_id),
                notification_type=notification_type,
            )
            return

        if status.status in ["SENT", "QUEUED"]:
            logger.warning(
                "notification_already_processed",
                notification_id=str(notification_id),
                notification_type=notification_type,
                status=status.status,
            )
            return

        self.queue.enqueue(
            "core.jobs.email_jobs.send_email_job",
            str(notification_id),
        )

        status.mark_queued()

        logger.info(
            "notification_queued",
            notification_id=str(notification_id),
            notification_type=notification_type,
        )

    def get_notification(self, notification_id: UUID) -> Notification:
        """Get a notification by ID.

        Args:
            notification_id: Notification ID.

        Returns:
            Notification instance.

        Raises:
            Notification.DoesNotExist: If notification not found.
        """
        return Notification.objects.get(notification_id=notification_id)

    def get_notifications_for_user(
        self,
        user: User,
        include_deleted: bool = False,
        limit: int = 100,
    ) -> QuerySet[Notification]:
        """Get notifications for a user (internal helper method).

        Args:
            user: User instance.
            include_deleted: Include soft-deleted notifications (default: False).
            limit: Maximum number of results.

        Returns:
            QuerySet of Notification instances.
        """
        queryset = Notification.objects.filter(user=user)

        if not include_deleted:
            queryset = queryset.filter(is_deleted=False)

        return queryset.order_by("-created_at")[:limit]

    def get_pending_email_statuses(
        self,
        limit: int = 100,
    ) -> QuerySet[NotificationStatus]:
        """Get pending EMAIL statuses that need to be queued.

        Args:
            limit: Maximum number of results.

        Returns:
            QuerySet of NotificationStatus instances.
        """
        return NotificationStatus.objects.filter(
            notification_type=NotificationType.EMAIL.value,
            status="PENDING",
        )[:limit]

    def retry_failed_notifications(self, max_retries: int = 3) -> int:
        """Retry failed EMAIL notifications that haven't exceeded max retries.

        Args:
            max_retries: Maximum number of retry attempts.

        Returns:
            Number of notifications requeued.
        """
        failed_statuses = NotificationStatus.objects.filter(
            notification_type=NotificationType.EMAIL.value,
            status="FAILED",
        ).select_related("notification")

        count = 0
        for status in failed_statuses:
            if status.can_retry(max_retries):
                status.status = "PENDING"
                status.error_message = None
                status.save(update_fields=["status", "error_message", "updated_at"])

                self.queue_notification(
                    status.notification_id,
                    status.notification_type,
                )
                count += 1

        logger.info(
            "notifications_requeued",
            count=count,
        )

        return count

    def get_my_notifications(
        self,
        include_deleted: bool = False,
    ) -> QuerySet[Notification]:
        """Get notifications for the authenticated user.

        This method uses the security context to retrieve the current user
        and returns their notifications.

        Args:
            include_deleted: Include soft-deleted notifications (default: False).

        Returns:
            QuerySet of Notification instances ordered by created_at DESC.

        Raises:
            PermissionDenied: If user is not authenticated or lacks required scope.
        """
        current_user = require_current_user()

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

        queryset = Notification.objects.filter(user_id=current_user.user_id)

        if not include_deleted:
            queryset = queryset.filter(is_deleted=False)

        logger.info(
            "user_notifications_queried",
            user_id=current_user.user_id,
            include_deleted=include_deleted,
        )

        return queryset.order_by("-created_at")

    def get_user_notifications(
        self,
        user_id: UUID,
        include_deleted: bool = False,
    ) -> QuerySet[Notification]:
        """Get notifications for a specific user by user_id (admin only).

        This method allows admins to retrieve notifications for any user.

        Args:
            user_id: UUID of the user whose notifications to retrieve.
            include_deleted: Include soft-deleted notifications (default: False).

        Returns:
            QuerySet of Notification instances ordered by created_at DESC.

        Raises:
            PermissionDenied: If current user lacks admin scope.
            UserNotFoundError: If user with given user_id does not exist.
        """
        current_user = require_current_user()

        if not current_user.has_scope("notification:admin"):
            logger.warning(
                "insufficient_scope_for_user_notifications",
                user_id=current_user.user_id,
                scopes=current_user.scopes,
                target_user_id=str(user_id),
            )
            raise PermissionDenied("Requires notification:admin scope")

        try:
            User.objects.get(user_id=user_id)
        except User.DoesNotExist as err:
            logger.warning(
                "target_user_not_found_for_notifications",
                target_user_id=str(user_id),
                requester_user_id=current_user.user_id,
            )
            raise UserNotFoundError(str(user_id)) from err

        queryset = Notification.objects.filter(user_id=user_id)

        if not include_deleted:
            queryset = queryset.filter(is_deleted=False)

        logger.info(
            "user_notifications_by_id_queried",
            target_user_id=str(user_id),
            requester_user_id=current_user.user_id,
            include_deleted=include_deleted,
        )

        return queryset.order_by("-created_at")

    def get_notification_for_user(
        self,
        notification_id: UUID,
    ) -> Notification:
        """Get a notification for the authenticated user with authorization check.

        Args:
            notification_id: Notification ID.

        Returns:
            Notification instance.

        Raises:
            Http404: If notification not found.
            PermissionDenied: If user is not authorized to view this notification.
        """
        current_user = require_current_user()

        try:
            notification = Notification.objects.get(notification_id=notification_id)
        except Notification.DoesNotExist as e:
            logger.warning(
                "notification_not_found",
                notification_id=str(notification_id),
                user_id=current_user.user_id,
            )
            raise Http404(f"Notification with ID {notification_id} not found") from e

        has_admin_scope = current_user.has_scope("notification:admin")
        is_owner = str(notification.user_id) == current_user.user_id

        if not has_admin_scope and not is_owner:
            logger.warning(
                "unauthorized_notification_access",
                notification_id=str(notification_id),
                user_id=current_user.user_id,
                owner_user_id=str(notification.user_id),
            )
            raise PermissionDenied("You can only view your own notifications")

        logger.info(
            "notification_retrieved",
            notification_id=str(notification_id),
            user_id=current_user.user_id,
        )

        return notification

    def delete_notification(self, notification_id: UUID) -> None:
        """Soft delete a notification with authorization and status checks.

        Args:
            notification_id: Notification ID.

        Raises:
            Http404: If notification not found.
            PermissionDenied: If user is not authorized to delete this notification.
            ConflictError: If EMAIL delivery is in 'QUEUED' status.
        """
        current_user = require_current_user()

        try:
            notification = Notification.objects.get(notification_id=notification_id)
        except Notification.DoesNotExist as e:
            logger.warning(
                "notification_not_found_for_deletion",
                notification_id=str(notification_id),
                user_id=current_user.user_id,
            )
            raise Http404(f"Notification with ID {notification_id} not found") from e

        has_admin_scope = current_user.has_scope("notification:admin")
        is_owner = str(notification.user_id) == current_user.user_id

        if not has_admin_scope and not is_owner:
            logger.warning(
                "unauthorized_notification_deletion",
                notification_id=str(notification_id),
                user_id=current_user.user_id,
                owner_user_id=str(notification.user_id),
            )
            raise PermissionDenied("You can only delete your own notifications")

        email_status = NotificationStatus.objects.filter(
            notification_id=notification_id,
            notification_type=NotificationType.EMAIL.value,
        ).first()

        if email_status and email_status.status == "QUEUED":
            logger.warning(
                "cannot_delete_queued_notification",
                notification_id=str(notification_id),
                user_id=current_user.user_id,
                status=email_status.status,
            )
            raise ConflictError(
                "Cannot delete notification while it is being processed",
                detail="EMAIL delivery is in 'QUEUED' status",
            )

        notification.is_deleted = True
        notification.save(update_fields=["is_deleted", "updated_at"])

        logger.info(
            "notification_deleted",
            notification_id=str(notification_id),
            user_id=current_user.user_id,
        )


notification_service = NotificationService()
