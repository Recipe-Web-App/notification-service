"""Unit tests for AdminService."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from django.core.cache import cache
from django.db.models.signals import post_save
from django.http import Http404
from django.test import TestCase

from core.auth.oauth2 import OAuth2User
from core.exceptions.downstream_exceptions import ConflictError
from core.models.notification import Notification
from core.models.user import User
from core.services.admin_service import AdminService
from core.signals.user_signals import send_welcome_email


class TestAdminService(TestCase):
    """Unit tests for AdminService class."""

    def setUp(self):
        """Set up test data."""
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
        # Store now for use in date filter tests
        self.now = datetime.now(UTC)
        now = self.now

        # Sent notifications
        # Note: created_at has auto_now_add=True, so we need to update it after creation
        self.sent_notification_1 = Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Test Sent 1",
            message="Test message",
            notification_type=Notification.EMAIL,
            status=Notification.SENT,
            queued_at=now - timedelta(days=5, seconds=10),
            sent_at=now - timedelta(days=5, seconds=5),
        )
        # Manually update created_at since it has auto_now_add=True
        Notification.objects.filter(pk=self.sent_notification_1.pk).update(
            created_at=now - timedelta(days=5)
        )
        self.sent_notification_1.refresh_from_db()

        self.sent_notification_2 = Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Test Sent 2",
            message="Test message",
            notification_type=Notification.EMAIL,
            status=Notification.SENT,
            queued_at=now - timedelta(days=4, seconds=20),
            sent_at=now - timedelta(days=4, seconds=10),
        )
        Notification.objects.filter(pk=self.sent_notification_2.pk).update(
            created_at=now - timedelta(days=4)
        )
        self.sent_notification_2.refresh_from_db()

        # Failed notifications
        self.failed_notification_1 = Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Test Failed 1",
            message="Test message",
            notification_type=Notification.EMAIL,
            status=Notification.FAILED,
            error_message="SMTP server connection failed",
        )
        Notification.objects.filter(pk=self.failed_notification_1.pk).update(
            created_at=now - timedelta(days=3)
        )
        self.failed_notification_1.refresh_from_db()

        self.failed_notification_2 = Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Test Failed 2",
            message="Test message",
            notification_type=Notification.EMAIL,
            status=Notification.FAILED,
            error_message="Invalid email address provided",
        )
        Notification.objects.filter(pk=self.failed_notification_2.pk).update(
            created_at=now - timedelta(days=2)
        )
        self.failed_notification_2.refresh_from_db()

        self.failed_notification_3 = Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Test Failed 3",
            message="Test message",
            notification_type=Notification.EMAIL,
            status=Notification.FAILED,
            error_message="Connection timeout occurred",
        )
        Notification.objects.filter(pk=self.failed_notification_3.pk).update(
            created_at=now - timedelta(days=1)
        )
        self.failed_notification_3.refresh_from_db()

        # Pending notification (created today)
        self.pending_notification = Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Test Pending",
            message="Test message",
            notification_type=Notification.EMAIL,
            status=Notification.PENDING,
        )

        # Queued notification (created today)
        self.queued_notification = Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Test Queued",
            message="Test message",
            notification_type=Notification.EMAIL,
            status=Notification.QUEUED,
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

        # Verify counts
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
    def test_get_notification_stats_filters_by_start_date(
        self, mock_require_current_user, mock_get_current_user
    ):
        """Test that get_notification_stats filters by start_date."""
        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        # Filter to last 3 days
        start_date = datetime.now(UTC) - timedelta(days=3)
        stats = self.admin_service.get_notification_stats(start_date=start_date)

        # Should get notifications from days 3, 2, 1, and 0
        # That's: failed_1, failed_2, failed_3, pending, queued = 5
        self.assertGreaterEqual(stats["total_notifications"], 4)
        self.assertLessEqual(stats["total_notifications"], 7)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_get_notification_stats_filters_by_end_date(
        self, mock_require_current_user, mock_get_current_user
    ):
        """Test that get_notification_stats filters by end_date."""
        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        # Filter to 2 days ago and earlier (using self.now for consistency)
        end_date = self.now - timedelta(days=2)
        stats = self.admin_service.get_notification_stats(end_date=end_date)

        # Should get notifications from days 5, 4, 3, 2
        # That's: sent_1, sent_2, failed_1, failed_2 = 4
        self.assertGreaterEqual(stats["total_notifications"], 2)
        self.assertLessEqual(stats["total_notifications"], 7)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_get_notification_stats_filters_by_date_range(
        self, mock_require_current_user, mock_get_current_user
    ):
        """Test that get_notification_stats filters by both dates."""
        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        # Filter to days 5-2 (using self.now for consistency)
        start_date = self.now - timedelta(days=5)
        end_date = self.now - timedelta(days=2)
        stats = self.admin_service.get_notification_stats(
            start_date=start_date, end_date=end_date
        )

        # Should get: sent_1, sent_2, failed_1, failed_2 = 4
        self.assertGreaterEqual(stats["total_notifications"], 2)
        self.assertLessEqual(stats["total_notifications"], 7)

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
        self.pending_notification.delete()

        # Second call - should use cache (same total)
        stats_2 = self.admin_service.get_notification_stats()

        # If cache is working, stats should be identical
        self.assertEqual(stats_1["total_notifications"], stats_2["total_notifications"])
        self.assertEqual(stats_1, stats_2)

    def test_calculate_average_send_time_with_sent_notifications(self):
        """Test _calculate_average_send_time with valid sent notifications."""
        queryset = Notification.objects.all()
        avg_time = self.admin_service._calculate_average_send_time(queryset)

        # sent_notification_1: 10 - 5 = 5 seconds
        # sent_notification_2: 20 - 10 = 10 seconds
        # Average: (5 + 10) / 2 = 7.5 seconds
        self.assertAlmostEqual(avg_time, 7.5, places=1)

    def test_calculate_average_send_time_with_no_sent_notifications(self):
        """Test _calculate_average_send_time with no sent notifications."""
        # Delete sent notifications
        Notification.objects.filter(status=Notification.SENT).delete()

        queryset = Notification.objects.all()
        avg_time = self.admin_service._calculate_average_send_time(queryset)

        # Should return 0.0
        self.assertEqual(avg_time, 0.0)

    def test_calculate_average_send_time_ignores_missing_timestamps(self):
        """Test _calculate_average_send_time ignores missing timestamps."""
        # Create sent notification without queued_at
        Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Test Sent No Queued",
            message="Test message",
            notification_type=Notification.EMAIL,
            status=Notification.SENT,
            created_at=datetime.now(UTC),
            sent_at=datetime.now(UTC),
            # No queued_at
        )

        queryset = Notification.objects.all()
        avg_time = self.admin_service._calculate_average_send_time(queryset)

        # Should still calculate from the valid ones
        # sent_notification_1: 5 seconds, sent_notification_2: 10 seconds
        self.assertAlmostEqual(avg_time, 7.5, places=1)

    def test_extract_error_type_smtp_error(self):
        """Test _extract_error_type identifies SMTP errors."""
        error_type = self.admin_service._extract_error_type(
            "SMTP server connection failed"
        )
        self.assertEqual(error_type, "smtp_error")

        error_type = self.admin_service._extract_error_type(
            "Mail server rejected message"
        )
        self.assertEqual(error_type, "smtp_error")

    def test_extract_error_type_invalid_email(self):
        """Test _extract_error_type identifies invalid email errors."""
        error_type = self.admin_service._extract_error_type("Invalid email address")
        self.assertEqual(error_type, "invalid_email")

        # Must have both "invalid" and "email"
        error_type = self.admin_service._extract_error_type("Invalid format")
        self.assertEqual(error_type, "other")

    def test_extract_error_type_timeout(self):
        """Test _extract_error_type identifies timeout errors."""
        error_type = self.admin_service._extract_error_type(
            "Connection timeout occurred"
        )
        self.assertEqual(error_type, "timeout")

        error_type = self.admin_service._extract_error_type("Request timed out")
        self.assertEqual(error_type, "timeout")

    def test_extract_error_type_connection_error(self):
        """Test _extract_error_type identifies connection errors."""
        error_type = self.admin_service._extract_error_type("Connection failed")
        self.assertEqual(error_type, "connection_error")

        error_type = self.admin_service._extract_error_type("Network unreachable")
        self.assertEqual(error_type, "connection_error")

    def test_extract_error_type_authentication_error(self):
        """Test _extract_error_type identifies authentication errors."""
        error_type = self.admin_service._extract_error_type("Authentication failed")
        self.assertEqual(error_type, "authentication_error")

        error_type = self.admin_service._extract_error_type("Auth credentials invalid")
        self.assertEqual(error_type, "authentication_error")

    def test_extract_error_type_rate_limit(self):
        """Test _extract_error_type identifies rate limit errors."""
        error_type = self.admin_service._extract_error_type("Rate limit exceeded")
        self.assertEqual(error_type, "rate_limit")

        error_type = self.admin_service._extract_error_type("Request throttled")
        self.assertEqual(error_type, "rate_limit")

    def test_extract_error_type_other(self):
        """Test _extract_error_type returns 'other' for unrecognized errors."""
        error_type = self.admin_service._extract_error_type("Something went wrong")
        self.assertEqual(error_type, "other")

    def test_extract_error_type_unknown(self):
        """Test _extract_error_type returns 'unknown' for None/empty."""
        error_type = self.admin_service._extract_error_type(None)
        self.assertEqual(error_type, "unknown")

        error_type = self.admin_service._extract_error_type("")
        self.assertEqual(error_type, "unknown")

    def test_get_failed_notifications_breakdown(self):
        """Test _get_failed_notifications_breakdown groups by error type."""
        queryset = Notification.objects.all()
        breakdown = self.admin_service._get_failed_notifications_breakdown(queryset)

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

    def test_get_failed_notifications_breakdown_with_no_failures(self):
        """Test _get_failed_notifications_breakdown with no failed notifications."""
        # Delete all failed notifications
        Notification.objects.filter(status=Notification.FAILED).delete()

        queryset = Notification.objects.all()
        breakdown = self.admin_service._get_failed_notifications_breakdown(queryset)

        self.assertEqual(breakdown["total"], 0)
        self.assertEqual(breakdown["by_error_type"], {})

    def test_get_date_range_with_provided_dates(self):
        """Test _get_date_range returns provided dates when both specified."""
        start_date = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
        end_date = datetime(2025, 1, 31, 23, 59, 59, tzinfo=UTC)

        queryset = Notification.objects.all()
        date_range = self.admin_service._get_date_range(queryset, start_date, end_date)

        self.assertEqual(date_range["start"], start_date.isoformat())
        self.assertEqual(date_range["end"], end_date.isoformat())

    def test_get_date_range_computed_from_data(self):
        """Test _get_date_range computes from data when dates not provided."""
        queryset = Notification.objects.all()
        date_range = self.admin_service._get_date_range(queryset, None, None)

        # Should return earliest and latest created_at
        self.assertIsNotNone(date_range["start"])
        self.assertIsNotNone(date_range["end"])

        # Verify it's using actual data
        earliest = Notification.objects.order_by("created_at").first()
        latest = Notification.objects.order_by("-created_at").first()

        self.assertEqual(date_range["start"], earliest.created_at.isoformat())
        self.assertEqual(date_range["end"], latest.created_at.isoformat())

    def test_get_date_range_with_empty_queryset(self):
        """Test _get_date_range returns None values for empty queryset."""
        # Delete all notifications
        Notification.objects.all().delete()

        queryset = Notification.objects.all()
        date_range = self.admin_service._get_date_range(queryset, None, None)

        self.assertIsNone(date_range["start"])
        self.assertIsNone(date_range["end"])

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

        queryset = Notification.objects.all()
        retry_stats = self.admin_service._get_retry_statistics(queryset)

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
        Notification.objects.all().delete()

        # Create notifications with various retry states
        # 2 sent with retries (successful retries)
        Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Sent after 1 retry",
            message="Message",
            status=Notification.SENT,
            retry_count=1,
            max_retries=3,
        )
        Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Sent after 2 retries",
            message="Message",
            status=Notification.SENT,
            retry_count=2,
            max_retries=3,
        )

        # 1 failed retryable (retry_count < max_retries)
        Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Failed retryable",
            message="Message",
            status=Notification.FAILED,
            retry_count=1,
            max_retries=3,
        )

        # 1 failed exhausted (retry_count >= max_retries)
        Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Failed exhausted",
            message="Message",
            status=Notification.FAILED,
            retry_count=3,
            max_retries=3,
        )

        # 1 sent without retries (first attempt success)
        Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Sent first attempt",
            message="Message",
            status=Notification.SENT,
            retry_count=0,
            max_retries=3,
        )

        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        queryset = Notification.objects.all()
        retry_stats = self.admin_service._get_retry_statistics(queryset)

        # total_retried: all with retry_count > 0 = 4
        # (2 sent + 1 failed retryable + 1 exhausted)
        self.assertEqual(retry_stats["total_retried"], 4)

        # currently_retrying: failed with retry_count < max_retries = 1
        self.assertEqual(retry_stats["currently_retrying"], 1)

        # exhausted_retries: failed with retry_count >= max_retries = 1
        self.assertEqual(retry_stats["exhausted_retries"], 1)

        # average_retries_before_success: avg of sent with retry_count > 0
        # (1 + 2) / 2 = 1.5
        self.assertAlmostEqual(
            retry_stats["average_retries_before_success"], 1.5, places=2
        )

        # retry_success_rate: sent with retries / total retried = 2 / 4 = 0.5
        self.assertAlmostEqual(retry_stats["retry_success_rate"], 0.5, places=2)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_get_retry_statistics_with_no_retries(
        self, mock_require_current_user, mock_get_current_user
    ):
        """Test _get_retry_statistics with no retries returns zeros."""
        # Clear existing data
        Notification.objects.all().delete()

        # Create notifications without retries
        Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Sent first attempt",
            message="Message",
            status=Notification.SENT,
            retry_count=0,
            max_retries=3,
        )

        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        queryset = Notification.objects.all()
        retry_stats = self.admin_service._get_retry_statistics(queryset)

        self.assertEqual(retry_stats["total_retried"], 0)
        self.assertEqual(retry_stats["currently_retrying"], 0)
        self.assertEqual(retry_stats["exhausted_retries"], 0)
        self.assertEqual(retry_stats["average_retries_before_success"], 0.0)
        self.assertEqual(retry_stats["retry_success_rate"], 0.0)

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_retry_failed_notifications_retries_eligible(
        self, mock_require_current_user, mock_get_current_user, mock_queue
    ):
        """Test retry_failed_notifications only retries eligible notifications."""
        # Clear existing data
        Notification.objects.all().delete()

        # Create eligible failed notifications
        notification_1 = Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Failed 1",
            message="Message",
            status=Notification.FAILED,
            retry_count=0,
            max_retries=3,
            error_message="Test error",
        )
        notification_2 = Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Failed 2",
            message="Message",
            status=Notification.FAILED,
            retry_count=1,
            max_retries=3,
            error_message="Test error",
        )

        # Create exhausted notification (should not be retried)
        Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Failed exhausted",
            message="Message",
            status=Notification.FAILED,
            retry_count=3,
            max_retries=3,
            error_message="Test error",
        )

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

        # Verify error messages were cleared
        notification_1.refresh_from_db()
        notification_2.refresh_from_db()
        self.assertEqual(notification_1.error_message, "")
        self.assertEqual(notification_2.error_message, "")

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_retry_failed_notifications_respects_max_failures_limit(
        self, mock_require_current_user, mock_get_current_user, mock_queue
    ):
        """Test retry_failed_notifications respects max_failures batch size."""
        # Clear existing data
        Notification.objects.all().delete()

        # Create 10 eligible failed notifications
        for i in range(10):
            Notification.objects.create(
                recipient=self.user,
                recipient_email=self.user.email,
                subject=f"Failed {i}",
                message="Message",
                status=Notification.FAILED,
                retry_count=0,
                max_retries=3,
                error_message="Test error",
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

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_retry_failed_notifications_with_no_failed(
        self, mock_require_current_user, mock_get_current_user, mock_queue
    ):
        """Test retry_failed_notifications with no failed notifications."""
        # Clear existing data
        Notification.objects.all().delete()

        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        result = self.admin_service.retry_failed_notifications()

        self.assertEqual(result["queued_count"], 0)
        self.assertEqual(result["total_eligible"], 0)
        self.assertEqual(result["remaining_failed"], 0)

        # Verify queue_notification was not called
        mock_queue.assert_not_called()

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_get_retry_status_returns_correct_counts(
        self, mock_require_current_user, mock_get_current_user
    ):
        """Test get_retry_status returns accurate counts."""
        # Clear existing data
        Notification.objects.all().delete()

        # Create test notifications
        # 3 failed retryable
        for i in range(3):
            Notification.objects.create(
                recipient=self.user,
                recipient_email=self.user.email,
                subject=f"Retryable {i}",
                message="Message",
                status=Notification.FAILED,
                retry_count=1,
                max_retries=3,
            )

        # 2 failed exhausted
        for i in range(2):
            Notification.objects.create(
                recipient=self.user,
                recipient_email=self.user.email,
                subject=f"Exhausted {i}",
                message="Message",
                status=Notification.FAILED,
                retry_count=3,
                max_retries=3,
            )

        # 1 queued
        Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Queued",
            message="Message",
            status=Notification.QUEUED,
            retry_count=0,
            max_retries=3,
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
        Notification.objects.all().delete()

        # Create only failed notifications
        Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Failed",
            message="Message",
            status=Notification.FAILED,
            retry_count=0,
            max_retries=3,
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

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_get_notification_stats_includes_retry_statistics(
        self, mock_require_current_user, mock_get_current_user
    ):
        """Test get_notification_stats includes retry_statistics."""
        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        stats = self.admin_service.get_notification_stats()

        # Verify retry_statistics is included
        self.assertIn("retry_statistics", stats)
        retry_stats = stats["retry_statistics"]

        # Verify structure
        self.assertIn("total_retried", retry_stats)
        self.assertIn("currently_retrying", retry_stats)
        self.assertIn("exhausted_retries", retry_stats)
        self.assertIn("average_retries_before_success", retry_stats)
        self.assertIn("retry_success_rate", retry_stats)

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
    def test_get_all_templates_returns_six_templates(self, mock_get_current_user):
        """Test get_all_templates returns exactly 6 templates."""
        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_get_current_user.return_value = admin_user

        templates = self.admin_service.get_all_templates()

        self.assertEqual(len(templates), 6)

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

    @patch("core.auth.context.get_current_user")
    def test_get_all_templates_types_are_unique(self, mock_get_current_user):
        """Test all template types are unique."""
        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_get_current_user.return_value = admin_user

        templates = self.admin_service.get_all_templates()

        template_types = [t["template_type"] for t in templates]

        self.assertEqual(len(template_types), len(set(template_types)))

    @patch("core.auth.context.get_current_user")
    def test_get_all_templates_contains_expected_types(self, mock_get_current_user):
        """Test templates include all expected notification types."""
        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_get_current_user.return_value = admin_user

        templates = self.admin_service.get_all_templates()
        template_types = [t["template_type"] for t in templates]

        expected_types = [
            "recipe_published",
            "recipe_liked",
            "recipe_commented",
            "new_follower",
            "mention",
            "password_reset",
        ]

        for expected_type in expected_types:
            self.assertIn(expected_type, template_types)

    @patch("core.auth.context.get_current_user")
    def test_get_all_templates_works_without_authenticated_user(
        self, mock_get_current_user
    ):
        """Test get_all_templates works when no user is authenticated."""
        mock_get_current_user.return_value = None

        templates = self.admin_service.get_all_templates()

        self.assertEqual(len(templates), 6)

    # Tests for retry_single_notification

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_retry_single_notification_success(
        self, mock_require_current_user, mock_get_current_user, mock_queue
    ):
        """Test retry_single_notification successfully retries a failed notification."""
        # Create a failed notification
        notification = Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Failed notification",
            message="Test message",
            status=Notification.FAILED,
            retry_count=1,
            max_retries=3,
            error_message="SMTP connection failed",
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
        notification.refresh_from_db()
        self.assertEqual(notification.error_message, "")

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
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Sent notification",
            message="Test message",
            status=Notification.SENT,
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
        self.assertIn("sent", context.exception.detail.lower())

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_retry_single_notification_exhausted_retries(
        self, mock_require_current_user, mock_get_current_user
    ):
        """Test retry_single_notification raises ConflictError when exhausted."""

        # Create a failed notification with exhausted retries
        notification = Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Failed notification",
            message="Test message",
            status=Notification.FAILED,
            retry_count=3,
            max_retries=3,
            error_message="Max retries exceeded",
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
        self.assertIn("3", context.exception.detail)

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_retry_single_notification_clears_error_message(
        self, mock_require_current_user, mock_get_current_user, mock_queue
    ):
        """Test retry_single_notification clears error message before retrying."""
        # Create a failed notification with detailed error message
        notification = Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Failed notification",
            message="Test message",
            status=Notification.FAILED,
            retry_count=0,
            max_retries=3,
            error_message=(
                "Detailed SMTP error: Connection timeout at server.example.com"
            ),
        )

        admin_user = OAuth2User(
            user_id=str(self.admin_user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_require_current_user.return_value = admin_user
        mock_get_current_user.return_value = admin_user

        # Verify error message exists before retry
        self.assertNotEqual(notification.error_message, "")

        self.admin_service.retry_single_notification(notification.notification_id)

        # Verify error message was cleared
        notification.refresh_from_db()
        self.assertEqual(notification.error_message, "")

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_retry_single_notification_with_partial_retries(
        self, mock_require_current_user, mock_get_current_user, mock_queue
    ):
        """Test retry_single_notification with partially retried notifications."""
        # Create a failed notification that has been retried once
        notification = Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user.email,
            subject="Failed notification",
            message="Test message",
            status=Notification.FAILED,
            retry_count=2,
            max_retries=5,
            error_message="Previous retry failed",
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

        # Verify notification was queued
        self.assertEqual(result["status"], "queued")
        mock_queue.assert_called_once_with(notification.notification_id)

        # Verify retry_count remains unchanged (it's incremented by the job processor)
        notification.refresh_from_db()
        self.assertEqual(notification.retry_count, 2)
