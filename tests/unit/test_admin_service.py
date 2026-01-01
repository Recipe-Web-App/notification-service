"""Unit tests for AdminService with two-table schema."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from django.core.cache import cache
from django.db.models.signals import post_save
from django.http import Http404
from django.test import TestCase
from django.utils import timezone

from core.auth.oauth2 import OAuth2User
from core.enums.notification import (
    NotificationCategory,
    NotificationStatusEnum,
    NotificationType,
)
from core.exceptions.downstream_exceptions import ConflictError
from core.models.notification import Notification
from core.models.notification_status import NotificationStatus
from core.models.user import User
from core.services.admin_service import MAX_RETRIES, AdminService
from core.signals.user_signals import send_welcome_email


class TestAdminService(TestCase):
    """Unit tests for AdminService class with two-table schema."""

    def setUp(self):
        """Set up test data using two-table schema."""
        cache.clear()

        # Disconnect signals to avoid side effects
        post_save.disconnect(send_welcome_email, sender=User)

        self.admin_service = AdminService()
        self.admin_user_id = uuid4()

        # Create test user
        self.user = User.objects.create(
            username="testuser",
            email="test@example.com",
            password_hash="hashed",
        )

        # Create test notifications with various states
        self.now = datetime.now(UTC)
        now = self.now

        # Helper to create notification with status
        def create_notif_with_status(
            category,
            notification_data,
            email_status,
            created_days_ago=0,
            error_message=None,
            queued_at=None,
            sent_at=None,
            retry_count=None,
        ):
            """Create notification and its EMAIL status record."""
            notif = Notification.objects.create(
                user=self.user,
                notification_category=category,
                notification_data=notification_data,
            )
            # Update created_at
            if created_days_ago:
                Notification.objects.filter(pk=notif.pk).update(
                    created_at=now - timedelta(days=created_days_ago)
                )
                notif.refresh_from_db()

            email_stat = NotificationStatus.objects.create(
                notification=notif,
                notification_type=NotificationType.EMAIL.value,
                status=email_status,
                recipient_email=self.user.email,
                error_message=error_message,
                retry_count=retry_count,
            )
            # Set timestamps based on status
            if queued_at:
                NotificationStatus.objects.filter(pk=email_stat.pk).update(
                    queued_at=queued_at
                )
            if sent_at:
                NotificationStatus.objects.filter(pk=email_stat.pk).update(
                    sent_at=sent_at
                )
            if email_status == NotificationStatusEnum.FAILED.value:
                NotificationStatus.objects.filter(pk=email_stat.pk).update(
                    failed_at=now
                )
            email_stat.refresh_from_db()

            # Also create IN_APP status (always SENT)
            NotificationStatus.objects.create(
                notification=notif,
                notification_type=NotificationType.IN_APP.value,
                status=NotificationStatusEnum.SENT.value,
                sent_at=now,
            )

            return notif, email_stat

        # Sent notifications
        self.sent_notification_1, self.sent_status_1 = create_notif_with_status(
            category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0", "recipe_title": "Test 1"},
            email_status=NotificationStatusEnum.SENT.value,
            created_days_ago=5,
            queued_at=now - timedelta(days=5, seconds=10),
            sent_at=now - timedelta(days=5, seconds=5),
        )

        self.sent_notification_2, self.sent_status_2 = create_notif_with_status(
            category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0", "recipe_title": "Test 2"},
            email_status=NotificationStatusEnum.SENT.value,
            created_days_ago=4,
            queued_at=now - timedelta(days=4, seconds=20),
            sent_at=now - timedelta(days=4, seconds=10),
        )

        # Failed notifications
        self.failed_notification_1, self.failed_status_1 = create_notif_with_status(
            category=NotificationCategory.RECIPE_COMMENTED.value,
            notification_data={"template_version": "1.0"},
            email_status=NotificationStatusEnum.FAILED.value,
            created_days_ago=3,
            error_message="SMTP server connection failed",
        )

        self.failed_notification_2, self.failed_status_2 = create_notif_with_status(
            category=NotificationCategory.RECIPE_COMMENTED.value,
            notification_data={"template_version": "1.0"},
            email_status=NotificationStatusEnum.FAILED.value,
            created_days_ago=2,
            error_message="Invalid email address provided",
        )

        self.failed_notification_3, self.failed_status_3 = create_notif_with_status(
            category=NotificationCategory.RECIPE_COMMENTED.value,
            notification_data={"template_version": "1.0"},
            email_status=NotificationStatusEnum.FAILED.value,
            created_days_ago=1,
            error_message="Connection timeout occurred",
        )

        # Pending notification (created today)
        self.pending_notification, self.pending_status = create_notif_with_status(
            category=NotificationCategory.NEW_FOLLOWER.value,
            notification_data={"template_version": "1.0"},
            email_status=NotificationStatusEnum.PENDING.value,
        )

        # Queued notification (created today)
        self.queued_notification, self.queued_status = create_notif_with_status(
            category=NotificationCategory.NEW_FOLLOWER.value,
            notification_data={"template_version": "1.0"},
            email_status=NotificationStatusEnum.QUEUED.value,
            queued_at=now,
        )

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_get_notification_stats_returns_correct_structure(
        self, mock_require_current_user, mock_get_current_user
    ):
        """Test that get_notification_stats returns all required fields."""
        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        stats = self.admin_service.get_notification_stats()

        # Verify structure
        self.assertIn("total_notifications", stats)
        self.assertIn("status_breakdown", stats)
        self.assertIn("type_breakdown", stats)
        self.assertIn("success_rate", stats)
        self.assertIn("average_send_time_seconds", stats)
        self.assertIn("failed_notifications", stats)
        self.assertIn("date_range", stats)

        # Verify status breakdown structure
        status_breakdown = stats["status_breakdown"]
        self.assertIn("pending", status_breakdown)
        self.assertIn("queued", status_breakdown)
        self.assertIn("sent", status_breakdown)
        self.assertIn("failed", status_breakdown)

        # Verify failed notifications structure
        failed = stats["failed_notifications"]
        self.assertIn("total", failed)
        self.assertIn("by_error_type", failed)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_get_notification_stats_calculates_totals_correctly(
        self, mock_require_current_user, mock_get_current_user
    ):
        """Test that get_notification_stats calculates totals correctly."""
        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        stats = self.admin_service.get_notification_stats()

        # Verify counts (EMAIL statuses only)
        self.assertEqual(stats["total_notifications"], 7)
        self.assertEqual(stats["status_breakdown"]["sent"], 2)
        self.assertEqual(stats["status_breakdown"]["failed"], 3)
        self.assertEqual(stats["status_breakdown"]["pending"], 1)
        self.assertEqual(stats["status_breakdown"]["queued"], 1)

        # Verify success rate (2 sent / 7 total)
        expected_rate = 2.0 / 7.0
        self.assertAlmostEqual(stats["success_rate"], expected_rate, places=4)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_get_notification_stats_uses_cache(
        self, mock_require_current_user, mock_get_current_user
    ):
        """Test that get_notification_stats uses cache on second call."""
        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        # First call - should compute
        stats_1 = self.admin_service.get_notification_stats()

        # Delete a notification to verify cache is used
        self.pending_status.delete()
        self.pending_notification.delete()

        # Second call - should use cache (same total)
        stats_2 = self.admin_service.get_notification_stats()

        # If cache is working, stats should be identical
        self.assertEqual(stats_1["total_notifications"], stats_2["total_notifications"])
        self.assertEqual(stats_1, stats_2)

    def test_calculate_average_send_time_with_sent_notifications(self):
        """Test _calculate_average_send_time with valid sent statuses."""
        status_queryset = NotificationStatus.objects.filter(
            notification_type=NotificationType.EMAIL.value
        )
        avg_time = self.admin_service._calculate_average_send_time(status_queryset)

        # sent_status_1: 10 - 5 = 5 seconds
        # sent_status_2: 20 - 10 = 10 seconds
        # Average: (5 + 10) / 2 = 7.5 seconds
        self.assertAlmostEqual(avg_time, 7.5, places=1)

    def test_calculate_average_send_time_with_no_sent_notifications(self):
        """Test _calculate_average_send_time with no sent statuses."""
        # Delete sent statuses
        NotificationStatus.objects.filter(
            status=NotificationStatusEnum.SENT.value
        ).delete()

        status_queryset = NotificationStatus.objects.filter(
            notification_type=NotificationType.EMAIL.value
        )
        avg_time = self.admin_service._calculate_average_send_time(status_queryset)

        # Should return 0.0
        self.assertEqual(avg_time, 0.0)

    def test_extract_error_type_smtp_error(self):
        """Test _extract_error_type identifies SMTP errors."""
        error_type = self.admin_service._extract_error_type(
            "SMTP server connection failed"
        )
        self.assertEqual(error_type, "smtp_error")

    def test_extract_error_type_invalid_email(self):
        """Test _extract_error_type identifies invalid email errors."""
        error_type = self.admin_service._extract_error_type("Invalid email address")
        self.assertEqual(error_type, "invalid_email")

    def test_extract_error_type_timeout(self):
        """Test _extract_error_type identifies timeout errors."""
        error_type = self.admin_service._extract_error_type(
            "Connection timeout occurred"
        )
        self.assertEqual(error_type, "timeout")

    def test_extract_error_type_unknown(self):
        """Test _extract_error_type returns 'unknown' for None/empty."""
        error_type = self.admin_service._extract_error_type(None)
        self.assertEqual(error_type, "unknown")

        error_type = self.admin_service._extract_error_type("")
        self.assertEqual(error_type, "unknown")

    def test_get_failed_notifications_breakdown(self):
        """Test _get_failed_notifications_breakdown groups by error type."""
        status_queryset = NotificationStatus.objects.filter(
            notification_type=NotificationType.EMAIL.value
        )
        breakdown = self.admin_service._get_failed_notifications_breakdown(
            status_queryset
        )

        # Verify structure
        self.assertIn("total", breakdown)
        self.assertIn("by_error_type", breakdown)

        # Verify counts
        self.assertEqual(breakdown["total"], 3)

        # Verify error types
        by_type = breakdown["by_error_type"]
        self.assertEqual(by_type.get("smtp_error", 0), 1)
        self.assertEqual(by_type.get("invalid_email", 0), 1)
        self.assertEqual(by_type.get("timeout", 0), 1)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_get_retry_statistics_structure(
        self, mock_require_current_user, mock_get_current_user
    ):
        """Test _get_retry_statistics returns correct structure."""
        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        status_queryset = NotificationStatus.objects.filter(
            notification_type=NotificationType.EMAIL.value
        )
        retry_stats = self.admin_service._get_retry_statistics(status_queryset)

        # Verify structure
        self.assertIn("total_retried", retry_stats)
        self.assertIn("currently_retrying", retry_stats)
        self.assertIn("exhausted_retries", retry_stats)
        self.assertIn("average_retries_before_success", retry_stats)
        self.assertIn("retry_success_rate", retry_stats)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_get_retry_statistics_with_retried_notifications(
        self, mock_require_current_user, mock_get_current_user
    ):
        """Test _get_retry_statistics calculates correctly with retries."""
        # Clear existing data
        NotificationStatus.objects.all().delete()
        Notification.objects.all().delete()

        now = timezone.now()

        # Create notifications with various retry states
        def create_test_notif(email_status, retry_count=None):
            notif = Notification.objects.create(
                user=self.user,
                notification_category=NotificationCategory.RECIPE_LIKED.value,
                notification_data={"template_version": "1.0"},
            )
            stat = NotificationStatus.objects.create(
                notification=notif,
                notification_type=NotificationType.EMAIL.value,
                status=email_status,
                retry_count=retry_count,
                recipient_email=self.user.email,
            )
            if email_status == NotificationStatusEnum.SENT.value:
                stat.sent_at = now
                stat.save(update_fields=["sent_at"])
            return notif, stat

        # 2 sent with retries (successful retries)
        create_test_notif(NotificationStatusEnum.SENT.value, retry_count=1)
        create_test_notif(NotificationStatusEnum.SENT.value, retry_count=2)

        # 1 failed retryable (retry_count < MAX_RETRIES)
        create_test_notif(NotificationStatusEnum.FAILED.value, retry_count=1)

        # 1 failed exhausted (retry_count >= MAX_RETRIES)
        create_test_notif(NotificationStatusEnum.FAILED.value, retry_count=MAX_RETRIES)

        # 1 sent without retries (first attempt success)
        create_test_notif(NotificationStatusEnum.SENT.value, retry_count=0)

        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        status_queryset = NotificationStatus.objects.filter(
            notification_type=NotificationType.EMAIL.value
        )
        retry_stats = self.admin_service._get_retry_statistics(status_queryset)

        # total_retried: all with retry_count > 0 = 4
        self.assertEqual(retry_stats["total_retried"], 4)

        # currently_retrying: failed with retry_count < MAX_RETRIES = 1
        self.assertEqual(retry_stats["currently_retrying"], 1)

        # exhausted_retries: failed with retry_count >= MAX_RETRIES = 1
        self.assertEqual(retry_stats["exhausted_retries"], 1)

        # average_retries_before_success: avg of sent with retry_count > 0
        # (1 + 2) / 2 = 1.5
        self.assertAlmostEqual(
            retry_stats["average_retries_before_success"], 1.5, places=2
        )

        # retry_success_rate: sent with retries / total retried = 2 / 4 = 0.5
        self.assertAlmostEqual(retry_stats["retry_success_rate"], 0.5, places=2)

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_retry_failed_notifications_retries_eligible(
        self, mock_require_current_user, mock_get_current_user, mock_queue
    ):
        """Test retry_failed_notifications only retries eligible statuses."""
        # Clear existing data
        NotificationStatus.objects.all().delete()
        Notification.objects.all().delete()

        def create_failed_notif(retry_count=None):
            notif = Notification.objects.create(
                user=self.user,
                notification_category=NotificationCategory.RECIPE_LIKED.value,
                notification_data={"template_version": "1.0"},
            )
            NotificationStatus.objects.create(
                notification=notif,
                notification_type=NotificationType.EMAIL.value,
                status=NotificationStatusEnum.FAILED.value,
                retry_count=retry_count,
                error_message="Test error",
                recipient_email=self.user.email,
            )
            return notif

        # Create eligible failed notifications
        create_failed_notif(retry_count=0)
        create_failed_notif(retry_count=1)

        # Create exhausted notification (should not be retried)
        create_failed_notif(retry_count=MAX_RETRIES)

        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        result = self.admin_service.retry_failed_notifications(max_failures=100)

        # Should retry only 2 eligible notifications
        self.assertEqual(result["queued_count"], 2)
        self.assertEqual(result["total_eligible"], 2)
        self.assertEqual(result["remaining_failed"], 0)

        # Verify queue_notification was called twice
        self.assertEqual(mock_queue.call_count, 2)

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_retry_failed_notifications_respects_max_failures_limit(
        self, mock_require_current_user, mock_get_current_user, mock_queue
    ):
        """Test retry_failed_notifications respects max_failures batch size."""
        # Clear existing data
        NotificationStatus.objects.all().delete()
        Notification.objects.all().delete()

        # Create 10 eligible failed notifications
        for _ in range(10):
            notif = Notification.objects.create(
                user=self.user,
                notification_category=NotificationCategory.RECIPE_LIKED.value,
                notification_data={"template_version": "1.0"},
            )
            NotificationStatus.objects.create(
                notification=notif,
                notification_type=NotificationType.EMAIL.value,
                status=NotificationStatusEnum.FAILED.value,
                retry_count=0,
                error_message="Test error",
                recipient_email=self.user.email,
            )

        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        # Retry only 5
        result = self.admin_service.retry_failed_notifications(max_failures=5)

        # Should retry only 5 notifications
        self.assertEqual(result["queued_count"], 5)
        self.assertEqual(result["total_eligible"], 10)
        self.assertEqual(result["remaining_failed"], 5)

        # Verify queue_notification was called 5 times
        self.assertEqual(mock_queue.call_count, 5)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_get_retry_status_returns_correct_counts(
        self, mock_require_current_user, mock_get_current_user
    ):
        """Test get_retry_status returns accurate counts."""
        # Clear existing data
        NotificationStatus.objects.all().delete()
        Notification.objects.all().delete()

        def create_notif_with_email_status(email_status, retry_count=None):
            notif = Notification.objects.create(
                user=self.user,
                notification_category=NotificationCategory.RECIPE_LIKED.value,
                notification_data={"template_version": "1.0"},
            )
            NotificationStatus.objects.create(
                notification=notif,
                notification_type=NotificationType.EMAIL.value,
                status=email_status,
                retry_count=retry_count,
                recipient_email=self.user.email,
            )
            return notif

        # 3 failed retryable
        for _ in range(3):
            create_notif_with_email_status(
                NotificationStatusEnum.FAILED.value, retry_count=1
            )

        # 2 failed exhausted
        for _ in range(2):
            create_notif_with_email_status(
                NotificationStatusEnum.FAILED.value, retry_count=MAX_RETRIES
            )

        # 1 queued
        create_notif_with_email_status(
            NotificationStatusEnum.QUEUED.value, retry_count=0
        )

        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        result = self.admin_service.get_retry_status()

        self.assertEqual(result["failed_retryable"], 3)
        self.assertEqual(result["failed_exhausted"], 2)
        self.assertEqual(result["currently_queued"], 1)
        self.assertFalse(result["safe_to_retry"])

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_get_retry_status_safe_to_retry_true(
        self, mock_require_current_user, mock_get_current_user
    ):
        """Test get_retry_status safe_to_retry=True when no queued."""
        # Clear existing data
        NotificationStatus.objects.all().delete()
        Notification.objects.all().delete()

        # Create only failed notification
        notif = Notification.objects.create(
            user=self.user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
        )
        NotificationStatus.objects.create(
            notification=notif,
            notification_type=NotificationType.EMAIL.value,
            status=NotificationStatusEnum.FAILED.value,
            retry_count=0,
            recipient_email=self.user.email,
        )

        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        result = self.admin_service.get_retry_status()

        self.assertEqual(result["currently_queued"], 0)
        self.assertTrue(result["safe_to_retry"])

    # Tests for retry_single_notification

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_retry_single_notification_success(
        self, mock_require_current_user, mock_get_current_user, mock_queue
    ):
        """Test retry_single_notification successfully retries a failed status."""
        # Create a failed notification
        notification = Notification.objects.create(
            user=self.user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
        )
        email_status = NotificationStatus.objects.create(
            notification=notification,
            notification_type=NotificationType.EMAIL.value,
            status=NotificationStatusEnum.FAILED.value,
            retry_count=1,
            error_message="SMTP connection failed",
            recipient_email=self.user.email,
        )

        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        result = self.admin_service.retry_single_notification(
            notification.notification_id
        )

        # Verify result structure
        self.assertEqual(result["notification_id"], str(notification.notification_id))
        self.assertEqual(result["status"], "queued")
        self.assertIn("retry", result["message"].lower())

        # Verify error message was cleared
        email_status.refresh_from_db()
        self.assertEqual(email_status.error_message, "")

        # Verify queue_notification was called
        mock_queue.assert_called_once_with(notification.notification_id)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_retry_single_notification_not_found(
        self, mock_require_current_user, mock_get_current_user
    ):
        """Test retry_single_notification raises Http404 for non-existent ID."""
        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        non_existent_id = uuid4()

        with self.assertRaises(Http404) as context:
            self.admin_service.retry_single_notification(non_existent_id)

        self.assertIn(str(non_existent_id), str(context.exception))

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_retry_single_notification_wrong_status(
        self, mock_require_current_user, mock_get_current_user
    ):
        """Test retry_single_notification raises ConflictError for non-failed."""
        # Create a sent notification (not failed)
        notification = Notification.objects.create(
            user=self.user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
        )
        NotificationStatus.objects.create(
            notification=notification,
            notification_type=NotificationType.EMAIL.value,
            status=NotificationStatusEnum.SENT.value,
            recipient_email=self.user.email,
        )

        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        with self.assertRaises(ConflictError) as context:
            self.admin_service.retry_single_notification(notification.notification_id)

        self.assertIn("failed", str(context.exception).lower())

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_retry_single_notification_exhausted_retries(
        self, mock_require_current_user, mock_get_current_user
    ):
        """Test retry_single_notification raises ConflictError when exhausted."""
        # Create a failed notification with exhausted retries
        notification = Notification.objects.create(
            user=self.user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
        )
        NotificationStatus.objects.create(
            notification=notification,
            notification_type=NotificationType.EMAIL.value,
            status=NotificationStatusEnum.FAILED.value,
            retry_count=MAX_RETRIES,
            error_message="Max retries exceeded",
            recipient_email=self.user.email,
        )

        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        with self.assertRaises(ConflictError) as context:
            self.admin_service.retry_single_notification(notification.notification_id)

        self.assertIn("exhausted", str(context.exception).lower())

    @patch("core.auth.context.get_current_user")
    def test_get_all_templates_returns_list(self, mock_get_current_user):
        """Test get_all_templates returns a list."""
        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_get_current_user.return_value = admin_user

        templates = self.admin_service.get_all_templates()

        self.assertIsInstance(templates, list)
        self.assertGreater(len(templates), 0)

    @patch("core.auth.context.get_current_user")
    def test_get_all_templates_each_has_required_fields(self, mock_get_current_user):
        """Test each template has all required metadata fields."""
        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_get_current_user.return_value = admin_user

        templates = self.admin_service.get_all_templates()

        required_keys = [
            "template_type",
            "display_name",
            "description",
            "required_fields",
            "endpoint",
        ]

        for template in templates:
            for key in required_keys:
                self.assertIn(key, template)
                self.assertIsNotNone(template[key])
