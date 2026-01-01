"""Component tests for retry failed notifications endpoint."""

from unittest.mock import patch
from uuid import uuid4

from django.core.cache import cache
from django.db.models.signals import post_save
from django.test import Client, TestCase

from core.auth.oauth2 import OAuth2User
from core.enums.notification import NotificationStatusEnum, NotificationType
from core.models.notification import Notification
from core.models.notification_status import NotificationStatus
from core.models.user import User
from core.signals.user_signals import send_welcome_email

# Max retries constant (matches admin_service.MAX_RETRIES)
MAX_RETRIES = 3


class TestRetryFailedNotificationsEndpoint(TestCase):
    """Component tests for POST /notifications/retry-failed."""

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()  # Clear cache to prevent test pollution

        self.client = Client()
        self.admin_id = uuid4()
        self.user_id = uuid4()
        self.url = "/api/v1/notification/notifications/retry-failed"

        # Disconnect signals to avoid side effects
        post_save.disconnect(send_welcome_email, sender=User)

        # Create test user
        self.user = User.objects.create(
            user_id=self.user_id,
            email="user@example.com",
            username="testuser",
            password_hash="test_hash",
        )

    def tearDown(self):
        """Clean up after tests."""
        # Clean up notifications and statuses
        NotificationStatus.objects.all().delete()
        Notification.objects.all().delete()
        post_save.connect(send_welcome_email, sender=User)

    def _create_notification_with_status(
        self,
        status,
        retry_count=None,
        error_message=None,
    ):
        """Helper to create a notification with EMAIL status.

        Args:
            status: Status value for the NotificationStatus
            retry_count: Retry count for the status
            error_message: Error message for the status

        Returns:
            Tuple of (Notification, NotificationStatus)
        """
        notification = Notification.objects.create(
            user=self.user,
            notification_category="TEST",
            notification_data={"test": True},
        )
        email_status = NotificationStatus.objects.create(
            notification=notification,
            notification_type=NotificationType.EMAIL.value,
            status=status,
            retry_count=retry_count,
            error_message=error_message,
            recipient_email=self.user.email,
        )
        return notification, email_status

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_admin_scope_returns_202(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
        mock_queue,
    ):
        """Test POST with admin scope returns HTTP 202 and queues notifications."""
        # Create 5 failed notifications with status
        for _ in range(5):
            self._create_notification_with_status(
                status=NotificationStatusEnum.FAILED.value,
                retry_count=0,
                error_message="Test error",
            )

        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 202)
        data = response.json()

        # Verify structure
        self.assertIn("queued_count", data)
        self.assertIn("remaining_failed", data)
        self.assertIn("total_eligible", data)
        self.assertIn("message", data)

        # Verify counts
        self.assertEqual(data["queued_count"], 5)
        self.assertEqual(data["remaining_failed"], 0)
        self.assertEqual(data["total_eligible"], 5)

        # Verify queue_notification was called for each
        self.assertEqual(mock_queue.call_count, 5)

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_without_admin_scope_returns_403(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
        mock_queue,
    ):
        """Test POST without admin scope returns HTTP 403."""
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)
        mock_require_current_user.return_value = user
        mock_get_current_user.return_value = user

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertEqual(data["error"], "forbidden")
        self.assertIn("notification:admin", data["detail"])

        # Verify queue_notification was not called
        mock_queue.assert_not_called()

    def test_post_without_authentication_returns_401(self):
        """Test POST without authentication returns HTTP 401."""
        response = self.client.post(self.url)

        # DRF may return 401 or 403 depending on configuration
        self.assertIn(response.status_code, [401, 403])

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_custom_max_failures(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
        mock_queue,
    ):
        """Test POST with custom max_failures parameter."""
        # Create 100 failed notifications with status
        for _ in range(100):
            self._create_notification_with_status(
                status=NotificationStatusEnum.FAILED.value,
                retry_count=0,
                error_message="Test error",
            )

        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        # Retry only 50
        response = self.client.post(f"{self.url}?max_failures=50")

        self.assertEqual(response.status_code, 202)
        data = response.json()

        # Verify only 50 were retried
        self.assertEqual(data["queued_count"], 50)
        self.assertEqual(data["remaining_failed"], 50)
        self.assertEqual(data["total_eligible"], 100)

        # Verify queue_notification was called 50 times
        self.assertEqual(mock_queue.call_count, 50)

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_invalid_max_failures_zero_returns_400(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
        mock_queue,
    ):
        """Test POST with max_failures=0 returns HTTP 400."""
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        response = self.client.post(f"{self.url}?max_failures=0")

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "bad_request")
        self.assertIn("between 1 and 1000", data["detail"])

        # Verify queue_notification was not called
        mock_queue.assert_not_called()

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_invalid_max_failures_over_limit_returns_400(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
        mock_queue,
    ):
        """Test POST with max_failures>1000 returns HTTP 400."""
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        response = self.client.post(f"{self.url}?max_failures=1001")

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "bad_request")
        self.assertIn("between 1 and 1000", data["detail"])

        # Verify queue_notification was not called
        mock_queue.assert_not_called()

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_invalid_max_failures_non_integer_returns_400(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
        mock_queue,
    ):
        """Test POST with non-integer max_failures returns HTTP 400."""
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        response = self.client.post(f"{self.url}?max_failures=invalid")

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "bad_request")
        self.assertIn("must be an integer", data["detail"])

        # Verify queue_notification was not called
        mock_queue.assert_not_called()

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_no_failed_notifications_returns_202_with_zero_count(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
        mock_queue,
    ):
        """Test POST with no failed notifications returns 202 with zero counts."""
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertEqual(data["queued_count"], 0)
        self.assertEqual(data["remaining_failed"], 0)
        self.assertEqual(data["total_eligible"], 0)

        # Verify queue_notification was not called
        mock_queue.assert_not_called()

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_only_retries_eligible_notifications(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
        mock_queue,
    ):
        """Test POST only retries notifications that haven't exhausted retries."""
        # Create failed notifications with varying retry counts
        # 3 eligible (retry_count < MAX_RETRIES)
        for _ in range(3):
            self._create_notification_with_status(
                status=NotificationStatusEnum.FAILED.value,
                retry_count=1,
                error_message="Test error",
            )

        # 2 exhausted (retry_count >= MAX_RETRIES)
        for _ in range(2):
            self._create_notification_with_status(
                status=NotificationStatusEnum.FAILED.value,
                retry_count=MAX_RETRIES,
                error_message="Test error",
            )

        # 1 sent (should not be retried)
        self._create_notification_with_status(
            status=NotificationStatusEnum.SENT.value,
            retry_count=0,
        )

        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 202)
        data = response.json()

        # Only 3 eligible notifications should be retried
        self.assertEqual(data["queued_count"], 3)
        self.assertEqual(data["total_eligible"], 3)

        # Verify queue_notification was called exactly 3 times
        self.assertEqual(mock_queue.call_count, 3)

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_clears_error_messages(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
        mock_queue,
    ):
        """Test POST clears error messages when retrying."""
        # Create failed notification with error message
        _notification, email_status = self._create_notification_with_status(
            status=NotificationStatusEnum.FAILED.value,
            retry_count=0,
            error_message="Original error message",
        )

        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 202)

        # Refresh from database
        email_status.refresh_from_db()

        # Error message should be cleared on the status record
        self.assertEqual(email_status.error_message, "")
