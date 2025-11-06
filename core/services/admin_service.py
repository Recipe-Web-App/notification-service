"""Admin service for administrative operations."""

from datetime import datetime
from typing import Any

from django.core.cache import cache
from django.db.models import Avg, Count, F, Q

import structlog

from core.auth.context import require_current_user
from core.models.notification import Notification
from core.services.notification_service import notification_service

logger = structlog.get_logger(__name__)


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

        # Build base queryset with date filtering
        queryset = Notification.objects.all()
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)

        # Get status breakdown
        status_counts = queryset.aggregate(
            total=Count("notification_id"),
            pending=Count("notification_id", filter=Q(status=Notification.PENDING)),
            queued=Count("notification_id", filter=Q(status=Notification.QUEUED)),
            sent=Count("notification_id", filter=Q(status=Notification.SENT)),
            failed=Count("notification_id", filter=Q(status=Notification.FAILED)),
        )

        # Get type breakdown
        type_breakdown = {
            Notification.EMAIL: queryset.filter(
                notification_type=Notification.EMAIL
            ).count(),
        }

        # Calculate success rate
        total = status_counts["total"]
        sent = status_counts["sent"]
        success_rate = float(sent) / float(total) if total > 0 else 0.0

        # Calculate average send time (in seconds)
        avg_send_time = self._calculate_average_send_time(queryset)

        # Get failed notifications breakdown
        failed_breakdown = self._get_failed_notifications_breakdown(queryset)

        # Get retry statistics
        retry_stats = self._get_retry_statistics(queryset)

        # Determine actual date range used
        date_range = self._get_date_range(queryset, start_date, end_date)

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

    def _calculate_average_send_time(self, queryset) -> float:
        """Calculate average time from queued to sent in seconds.

        Args:
            queryset: Base queryset to calculate from

        Returns:
            Average send time in seconds, or 0.0 if no sent notifications
        """
        # Only include sent notifications with both queued_at and sent_at
        sent_notifications = queryset.filter(
            status=Notification.SENT,
            queued_at__isnull=False,
            sent_at__isnull=False,
        )

        if not sent_notifications.exists():
            return 0.0

        # Calculate average time difference in Python (database-agnostic)
        # Extract() with epoch doesn't work on SQLite, so we'll compute in Python
        total_seconds = 0.0
        count = 0

        for notification in sent_notifications:
            if notification.sent_at and notification.queued_at:
                time_diff = notification.sent_at - notification.queued_at
                total_seconds += time_diff.total_seconds()
                count += 1

        return total_seconds / count if count > 0 else 0.0

    def _get_failed_notifications_breakdown(self, queryset) -> dict[str, Any]:
        """Get breakdown of failed notifications by error type.

        Args:
            queryset: Base queryset to analyze

        Returns:
            Dict with 'total' and 'by_error_type' keys
        """
        failed_queryset = queryset.filter(status=Notification.FAILED)
        total_failed = failed_queryset.count()

        # Group by error type
        # Parse error_message to extract error types
        by_error_type: dict[str, int] = {}

        for notification in failed_queryset:
            error_type = self._extract_error_type(notification.error_message)
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

    def _get_retry_statistics(self, queryset) -> dict[str, Any]:
        """Get retry statistics for notifications.

        Args:
            queryset: Base queryset to analyze

        Returns:
            Dict with retry metrics:
            - total_retried: Count of notifications that have been retried
            - currently_retrying: Failed notifications that can still be retried
            - exhausted_retries: Failed notifications at max retries
            - average_retries_before_success: Avg retry_count for successful retries
            - retry_success_rate: Success rate for retried notifications
        """
        # Total notifications that have been retried (retry_count > 0)
        total_retried = queryset.filter(retry_count__gt=0).count()

        # Failed notifications that can still be retried
        currently_retrying = queryset.filter(
            status=Notification.FAILED,
            retry_count__lt=F("max_retries"),
        ).count()

        # Failed notifications that have exhausted retries
        exhausted_retries = queryset.filter(
            status=Notification.FAILED,
            retry_count__gte=F("max_retries"),
        ).count()

        # Average retries before success (for retried notifications)
        retried_and_sent = queryset.filter(
            status=Notification.SENT,
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

        # Query all eligible failed notifications
        eligible_notifications = Notification.objects.filter(
            status=Notification.FAILED,
            retry_count__lt=F("max_retries"),
        ).order_by("created_at")

        total_eligible = eligible_notifications.count()

        # Limit to batch size
        notifications_to_retry = eligible_notifications[:max_failures]

        queued_count = 0
        for notification in notifications_to_retry:
            # Clear error message and enqueue
            notification.error_message = ""
            notification.save(update_fields=["error_message"])

            # Queue the notification (this will set status to QUEUED)
            notification_service.queue_notification(notification.notification_id)
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

        Returns:
            Dict containing:
            - failed_retryable: Count of FAILED notifications that can be retried
            - failed_exhausted: Count of FAILED notifications at max retries
            - currently_queued: Count of notifications currently queued
            - safe_to_retry: Boolean indicating if safe to queue more retries
        """
        current_user = require_current_user()

        logger.info(
            "retry_status_requested",
            user_id=current_user.user_id,
        )

        # Count failed notifications that can be retried
        failed_retryable = Notification.objects.filter(
            status=Notification.FAILED,
            retry_count__lt=F("max_retries"),
        ).count()

        # Count failed notifications that have exhausted retries
        failed_exhausted = Notification.objects.filter(
            status=Notification.FAILED,
            retry_count__gte=F("max_retries"),
        ).count()

        # Count notifications currently queued for processing
        currently_queued = Notification.objects.filter(
            status=Notification.QUEUED,
        ).count()

        # Safe to retry if no notifications are currently queued
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


# Singleton instance
admin_service = AdminService()
