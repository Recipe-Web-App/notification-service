"""Admin service for administrative operations.

This service provides admin-specific operations for the notification system,
using the normalized two-table design:
- Notification: User-facing notification data
- NotificationStatus: Per-channel delivery tracking
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from django.core.cache import cache
from django.db.models import Avg, Count, Q
from django.http import Http404

import structlog

from core.auth.context import get_current_user, require_current_user
from core.constants.templates import TEMPLATE_REGISTRY
from core.enums.notification import NotificationStatusEnum, NotificationType
from core.exceptions.downstream_exceptions import ConflictError
from core.models.notification import Notification
from core.models.notification_status import NotificationStatus
from core.services.notification_service import notification_service

logger = structlog.get_logger(__name__)

# Max retries constant (also defined in NotificationStatus model)
MAX_RETRIES = 3


class AdminService:
    """Service for admin-specific operations.

    Provides high-level API for administrative tasks such as statistics,
    bulk operations, and system-wide queries.
    """

    CACHE_TTL = 300  # 5 minutes

    def get_notification_stats(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """Get comprehensive notification statistics.

        Uses the two-table design where delivery status is tracked in
        NotificationStatus table. Stats are computed from EMAIL channel
        status records.

        Args:
            start_date: Optional start date for filtering (inclusive)
            end_date: Optional end date for filtering (inclusive)

        Returns:
            Dictionary containing:
            - total_notifications: Total count
            - status_breakdown: Dict with counts per status
            - type_breakdown: Dict with counts per type
            - success_rate: Float representing sent / total
            - average_send_time_seconds: Avg time from queued to sent
            - failed_notifications: Dict with total and by_error_type breakdown
            - date_range: Dict with start and end dates
        """
        current_user = require_current_user()

        logger.info(
            "notification_stats_requested",
            user_id=current_user.user_id,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
        )

        # Build cache key
        cache_key = self._build_cache_key(start_date, end_date)

        # Check cache
        cached_stats: dict[str, Any] | None = cache.get(cache_key)
        if cached_stats is not None:
            logger.info(
                "notification_stats_cache_hit",
                user_id=current_user.user_id,
                cache_key=cache_key,
            )
            return cached_stats

        # Build base queryset for Notifications with date filtering
        notif_queryset = Notification.objects.all()
        if start_date:
            notif_queryset = notif_queryset.filter(created_at__gte=start_date)
        if end_date:
            notif_queryset = notif_queryset.filter(created_at__lte=end_date)

        # Get notification IDs for joining with status table
        notif_ids = notif_queryset.values_list("notification_id", flat=True)

        # Build status queryset - filter to EMAIL channel only for delivery stats
        status_queryset = NotificationStatus.objects.filter(
            notification_id__in=notif_ids,
            notification_type=NotificationType.EMAIL.value,
        )

        # Get status breakdown from NotificationStatus table
        status_counts = status_queryset.aggregate(
            total=Count("id"),
            pending=Count("id", filter=Q(status=NotificationStatusEnum.PENDING.value)),
            queued=Count("id", filter=Q(status=NotificationStatusEnum.QUEUED.value)),
            sent=Count("id", filter=Q(status=NotificationStatusEnum.SENT.value)),
            failed=Count("id", filter=Q(status=NotificationStatusEnum.FAILED.value)),
        )

        # Get type breakdown (count EMAIL status records)
        type_breakdown = {
            NotificationType.EMAIL.value: status_counts["total"],
        }

        # Calculate success rate
        total = status_counts["total"]
        sent = status_counts["sent"]
        success_rate = float(sent) / float(total) if total > 0 else 0.0

        # Calculate average send time (in seconds)
        avg_send_time = self._calculate_average_send_time(status_queryset)

        # Get failed notifications breakdown
        failed_breakdown = self._get_failed_notifications_breakdown(status_queryset)

        # Get retry statistics
        retry_stats = self._get_retry_statistics(status_queryset)

        # Determine actual date range used (from Notification table)
        date_range = self._get_date_range(notif_queryset, start_date, end_date)

        # Build response
        stats = {
            "total_notifications": total,
            "status_breakdown": {
                "pending": status_counts["pending"],
                "queued": status_counts["queued"],
                "sent": status_counts["sent"],
                "failed": status_counts["failed"],
            },
            "type_breakdown": type_breakdown,
            "success_rate": success_rate,
            "average_send_time_seconds": avg_send_time,
            "failed_notifications": failed_breakdown,
            "retry_statistics": retry_stats,
            "date_range": date_range,
        }

        # Cache the result
        cache.set(cache_key, stats, self.CACHE_TTL)

        logger.info(
            "notification_stats_computed",
            user_id=current_user.user_id,
            total=total,
            sent=sent,
            failed=status_counts["failed"],
            cache_key=cache_key,
        )

        return stats

    def _build_cache_key(
        self, start_date: datetime | None, end_date: datetime | None
    ) -> str:
        """Build cache key for stats query.

        Args:
            start_date: Start date or None
            end_date: End date or None

        Returns:
            Cache key string
        """
        start_str = start_date.isoformat() if start_date else "all"
        end_str = end_date.isoformat() if end_date else "all"
        return f"admin:notification_stats:{start_str}:{end_str}"

    def _calculate_average_send_time(self, status_queryset) -> float:
        """Calculate average time from queued to sent in seconds.

        Args:
            status_queryset: NotificationStatus queryset to calculate from

        Returns:
            Average send time in seconds, or 0.0 if no sent notifications
        """
        # Only include sent status records with both queued_at and sent_at
        sent_statuses = status_queryset.filter(
            status=NotificationStatusEnum.SENT.value,
            queued_at__isnull=False,
            sent_at__isnull=False,
        )

        if not sent_statuses.exists():
            return 0.0

        # Calculate average time difference in Python (database-agnostic)
        # Extract() with epoch doesn't work on SQLite, so we'll compute in Python
        total_seconds = 0.0
        count = 0

        for status in sent_statuses:
            if status.sent_at and status.queued_at:
                time_diff = status.sent_at - status.queued_at
                total_seconds += time_diff.total_seconds()
                count += 1

        return total_seconds / count if count > 0 else 0.0

    def _get_failed_notifications_breakdown(self, status_queryset) -> dict[str, Any]:
        """Get breakdown of failed notifications by error type.

        Args:
            status_queryset: NotificationStatus queryset to analyze

        Returns:
            Dict with 'total' and 'by_error_type' keys
        """
        failed_statuses = status_queryset.filter(
            status=NotificationStatusEnum.FAILED.value
        )
        total_failed = failed_statuses.count()

        # Group by error type
        # Parse error_message to extract error types
        by_error_type: dict[str, int] = {}

        for status in failed_statuses:
            error_type = self._extract_error_type(status.error_message)
            by_error_type[error_type] = by_error_type.get(error_type, 0) + 1

        return {
            "total": total_failed,
            "by_error_type": by_error_type,
        }

    def _extract_error_type(self, error_message: str) -> str:
        """Extract error type from error message.

        Args:
            error_message: Full error message string

        Returns:
            Error type string (e.g., 'smtp_error', 'invalid_email', 'timeout')
        """
        if not error_message:
            return "unknown"

        error_lower = error_message.lower()

        # Check for common error patterns (using dict mapping to reduce returns)
        error_patterns = {
            "smtp_error": ["smtp", "mail server"],
            "invalid_email": ["invalid", "email"],
            "timeout": ["timeout", "timed out"],
            "connection_error": ["connection", "network"],
            "authentication_error": ["authentication", "auth"],
            "rate_limit": ["rate limit", "throttle"],
        }

        for error_type, patterns in error_patterns.items():
            if error_type == "invalid_email":
                # Special case: needs both patterns
                if all(p in error_lower for p in patterns):
                    return error_type
            elif any(p in error_lower for p in patterns):
                return error_type

        return "other"

    def _get_date_range(
        self,
        queryset,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> dict[str, str | None]:
        """Get the actual date range used for the query.

        Args:
            queryset: Queryset to analyze
            start_date: Requested start date
            end_date: Requested end date

        Returns:
            Dict with 'start' and 'end' ISO format strings or None
        """
        if not queryset.exists():
            return {"start": None, "end": None}

        # If dates were provided, use them
        if start_date and end_date:
            return {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            }

        # Otherwise, compute from actual data (get min/max dates)
        first_notification = queryset.order_by("created_at").first()
        last_notification = queryset.order_by("-created_at").first()

        return {
            "start": first_notification.created_at.isoformat()
            if first_notification
            else None,
            "end": last_notification.created_at.isoformat()
            if last_notification
            else None,
        }

    def _get_retry_statistics(self, status_queryset) -> dict[str, Any]:
        """Get retry statistics for notifications.

        Args:
            status_queryset: NotificationStatus queryset to analyze

        Returns:
            Dict with retry metrics:
            - total_retried: Count of statuses that have been retried
            - currently_retrying: Failed statuses that can still be retried
            - exhausted_retries: Failed statuses at max retries
            - average_retries_before_success: Avg retry_count for successful retries
            - retry_success_rate: Success rate for retried statuses
        """
        # Total statuses that have been retried (retry_count > 0)
        total_retried = status_queryset.filter(retry_count__gt=0).count()

        # Failed statuses that can still be retried (retry_count < MAX_RETRIES)
        currently_retrying = status_queryset.filter(
            status=NotificationStatusEnum.FAILED.value,
            retry_count__lt=MAX_RETRIES,
        ).count()

        # Failed statuses that have exhausted retries
        exhausted_retries = status_queryset.filter(
            status=NotificationStatusEnum.FAILED.value,
            retry_count__gte=MAX_RETRIES,
        ).count()

        # Average retries before success (for retried statuses)
        retried_and_sent = status_queryset.filter(
            status=NotificationStatusEnum.SENT.value,
            retry_count__gt=0,
        )
        avg_retries = retried_and_sent.aggregate(avg=Avg("retry_count"))["avg"] or 0.0

        # Retry success rate (retried and sent / total retried)
        retried_sent_count = retried_and_sent.count()
        retry_success_rate = (
            float(retried_sent_count) / float(total_retried)
            if total_retried > 0
            else 0.0
        )

        return {
            "total_retried": total_retried,
            "currently_retrying": currently_retrying,
            "exhausted_retries": exhausted_retries,
            "average_retries_before_success": float(avg_retries),
            "retry_success_rate": retry_success_rate,
        }

    def retry_failed_notifications(self, max_failures: int = 100) -> dict[str, Any]:
        """Retry failed notifications that haven't exceeded max retries.

        Queries NotificationStatus for EMAIL channel failures and queues
        them for retry.

        Args:
            max_failures: Maximum number of notifications to retry (batch size limit)

        Returns:
            Dict containing:
            - queued_count: Number of notifications queued for retry
            - remaining_failed: Number of eligible failed notifications not retried
            - total_eligible: Total eligible failed notifications
        """
        current_user = require_current_user()

        logger.info(
            "retry_failed_notifications_requested",
            user_id=current_user.user_id,
            max_failures=max_failures,
        )

        # Query all eligible failed EMAIL status records
        eligible_statuses = (
            NotificationStatus.objects.filter(
                notification_type=NotificationType.EMAIL.value,
                status=NotificationStatusEnum.FAILED.value,
            )
            .filter(Q(retry_count__isnull=True) | Q(retry_count__lt=MAX_RETRIES))
            .select_related("notification")
            .order_by("created_at")
        )

        total_eligible = eligible_statuses.count()

        # Limit to batch size
        statuses_to_retry = eligible_statuses[:max_failures]

        queued_count = 0
        for status in statuses_to_retry:
            # Clear error message and enqueue
            status.error_message = ""
            status.save(update_fields=["error_message"])

            # Queue the notification (this will set status to QUEUED)
            notification_service.queue_notification(status.notification_id)
            queued_count += 1

        remaining_failed = total_eligible - queued_count

        logger.info(
            "retry_failed_notifications_completed",
            user_id=current_user.user_id,
            queued_count=queued_count,
            total_eligible=total_eligible,
            remaining_failed=remaining_failed,
        )

        return {
            "queued_count": queued_count,
            "remaining_failed": remaining_failed,
            "total_eligible": total_eligible,
        }

    def get_retry_status(self) -> dict[str, Any]:
        """Get current retry status for failed notifications.

        Queries NotificationStatus for EMAIL channel status counts.

        Returns:
            Dict containing:
            - failed_retryable: Count of FAILED statuses that can be retried
            - failed_exhausted: Count of FAILED statuses at max retries
            - currently_queued: Count of statuses currently queued
            - safe_to_retry: Boolean indicating if safe to queue more retries
        """
        current_user = require_current_user()

        logger.info(
            "retry_status_requested",
            user_id=current_user.user_id,
        )

        # Base queryset for EMAIL channel
        email_statuses = NotificationStatus.objects.filter(
            notification_type=NotificationType.EMAIL.value
        )

        # Count failed statuses that can be retried
        failed_retryable = (
            email_statuses.filter(
                status=NotificationStatusEnum.FAILED.value,
            )
            .filter(Q(retry_count__isnull=True) | Q(retry_count__lt=MAX_RETRIES))
            .count()
        )

        # Count failed statuses that have exhausted retries
        failed_exhausted = email_statuses.filter(
            status=NotificationStatusEnum.FAILED.value,
            retry_count__gte=MAX_RETRIES,
        ).count()

        # Count statuses currently queued for processing
        currently_queued = email_statuses.filter(
            status=NotificationStatusEnum.QUEUED.value,
        ).count()

        # Safe to retry if no statuses are currently queued
        safe_to_retry = currently_queued == 0

        logger.info(
            "retry_status_computed",
            user_id=current_user.user_id,
            failed_retryable=failed_retryable,
            failed_exhausted=failed_exhausted,
            currently_queued=currently_queued,
            safe_to_retry=safe_to_retry,
        )

        return {
            "failed_retryable": failed_retryable,
            "failed_exhausted": failed_exhausted,
            "currently_queued": currently_queued,
            "safe_to_retry": safe_to_retry,
        }

    def retry_single_notification(self, notification_id: UUID) -> dict[str, Any]:
        """Retry a single failed notification.

        Retries the EMAIL channel status for the given notification.

        Args:
            notification_id: UUID of the notification to retry

        Returns:
            Dict containing:
            - notification_id: UUID of the notification
            - status: Current status after queueing (should be "queued")
            - message: Success message

        Raises:
            Http404: If notification or its EMAIL status doesn't exist
            ConflictError: If notification cannot be retried (wrong status or
                          retries exhausted)
        """
        current_user = require_current_user()

        logger.info(
            "retry_single_notification_called",
            user_id=current_user.user_id,
            notification_id=str(notification_id),
        )

        # Fetch the notification
        try:
            notification = Notification.objects.get(notification_id=notification_id)
        except Notification.DoesNotExist as exc:
            logger.warning(
                "notification_not_found_for_retry",
                user_id=current_user.user_id,
                notification_id=str(notification_id),
            )
            raise Http404(f"Notification with ID {notification_id} not found") from exc

        # Fetch the EMAIL status for this notification
        try:
            email_status = NotificationStatus.objects.get(
                notification=notification,
                notification_type=NotificationType.EMAIL.value,
            )
        except NotificationStatus.DoesNotExist as exc:
            logger.warning(
                "email_status_not_found_for_retry",
                user_id=current_user.user_id,
                notification_id=str(notification_id),
            )
            raise Http404(
                f"EMAIL status for notification {notification_id} not found"
            ) from exc

        # Validate status is in FAILED status
        if email_status.status != NotificationStatusEnum.FAILED.value:
            logger.warning(
                "cannot_retry_notification_wrong_status",
                user_id=current_user.user_id,
                notification_id=str(notification_id),
                current_status=email_status.status,
            )
            raise ConflictError(
                "Cannot retry notification that is not in failed status",
                detail=f"Current status is '{email_status.status}'",
            )

        # Check if status can still be retried
        if not email_status.can_retry(MAX_RETRIES):
            logger.warning(
                "cannot_retry_notification_exhausted",
                user_id=current_user.user_id,
                notification_id=str(notification_id),
                retry_count=email_status.retry_count,
                max_retries=MAX_RETRIES,
            )
            raise ConflictError(
                "Cannot retry notification - retry limit exhausted",
                detail=(
                    f"Retry count ({email_status.retry_count}) >= "
                    f"max retries ({MAX_RETRIES})"
                ),
            )

        # Clear error message before retry
        email_status.error_message = ""
        email_status.save(update_fields=["error_message"])

        # Queue the notification for retry
        notification_service.queue_notification(notification_id)

        logger.info(
            "notification_queued_for_retry",
            user_id=current_user.user_id,
            notification_id=str(notification_id),
            retry_count=email_status.retry_count,
        )

        return {
            "notification_id": str(notification_id),
            "status": "queued",
            "message": "Notification queued for retry",
        }

    def get_all_templates(self) -> list[dict]:
        """Get list of all available notification templates.

        Returns:
            List of template metadata dictionaries containing:
            - template_type: Template identifier
            - display_name: Human-readable name
            - description: Template description
            - required_fields: List of required fields
            - endpoint: API endpoint for this template
        """
        current_user = get_current_user()

        logger.info(
            "template_list_requested",
            user_id=current_user.user_id if current_user else None,
            template_count=len(TEMPLATE_REGISTRY),
        )

        return TEMPLATE_REGISTRY


# Singleton instance
admin_service = AdminService()
