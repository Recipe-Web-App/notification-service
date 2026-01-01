"""Component tests for notification retry status endpoint."""

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


class TestNotificationRetryStatusEndpoint(TestCase):
    """Component tests for GET /notifications/retry-status."""

    def setUp(self):
        """Set up test fixtures."""
        cache.clear()  # Clear cache to prevent test pollution

        self.client = Client()
        self.admin_id = uuid4()
        self.user_id = uuid4()
        self.url = "/api/v1/notification/notifications/retry-status"

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
        notification_category="TEST",
    ):
        """Helper to create a notification with EMAIL status.

        Args:
            status: Status value for the NotificationStatus
            retry_count: Retry count for the status (None or int)
            notification_category: Category for the notification

        Returns:
            Tuple of (Notification, NotificationStatus)
        """
        notification = Notification.objects.create(
            user=self.user,
            notification_category=notification_category,
            notification_data={"test": True},
        )
        email_status = NotificationStatus.objects.create(
            notification=notification,
            notification_type=NotificationType.EMAIL.value,
            status=status,
            retry_count=retry_count,
            recipient_email=self.user.email,
        )
        return notification, email_status

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_admin_scope_returns_200(
        self, mock_authenticate, mock_require_current_user, mock_get_current_user
    ):
        """Test GET with admin scope returns HTTP 200 with retry status."""
        # Create test notifications with statuses
        # 3 failed retryable (retry_count < MAX_RETRIES)
        for _ in range(3):
            self._create_notification_with_status(
                status=NotificationStatusEnum.FAILED.value,
                retry_count=1,
            )

        # 2 failed exhausted (retry_count >= MAX_RETRIES)
        for _ in range(2):
            self._create_notification_with_status(
                status=NotificationStatusEnum.FAILED.value,
                retry_count=MAX_RETRIES,
            )

        # 1 queued
        self._create_notification_with_status(
            status=NotificationStatusEnum.QUEUED.value,
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

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify structure
        self.assertIn("failed_retryable", data)
        self.assertIn("failed_exhausted", data)
        self.assertIn("currently_queued", data)
        self.assertIn("safe_to_retry", data)

        # Verify counts
        self.assertEqual(data["failed_retryable"], 3)
        self.assertEqual(data["failed_exhausted"], 2)
        self.assertEqual(data["currently_queued"], 1)
        self.assertFalse(data["safe_to_retry"])  # False because queued > 0

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_without_admin_scope_returns_403(
        self, mock_authenticate, mock_require_current_user, mock_get_current_user
    ):
        """Test GET without admin scope returns HTTP 403."""
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)
        mock_require_current_user.return_value = user
        mock_get_current_user.return_value = user

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertEqual(data["error"], "forbidden")
        self.assertIn("notification:admin", data["detail"])

    def test_get_without_authentication_returns_401(self):
        """Test GET without authentication returns HTTP 401."""
        response = self.client.get(self.url)

        # DRF may return 401 or 403 depending on configuration
        self.assertIn(response.status_code, [401, 403])

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_no_queued_returns_safe_to_retry_true(
        self, mock_authenticate, mock_require_current_user, mock_get_current_user
    ):
        """Test GET with no queued notifications returns safe_to_retry=true."""
        # Create only failed notifications (no queued)
        self._create_notification_with_status(
            status=NotificationStatusEnum.FAILED.value,
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

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["currently_queued"], 0)
        self.assertTrue(data["safe_to_retry"])

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_queued_returns_safe_to_retry_false(
        self, mock_authenticate, mock_require_current_user, mock_get_current_user
    ):
        """Test GET with queued notifications returns safe_to_retry=false."""
        # Create queued notification
        self._create_notification_with_status(
            status=NotificationStatusEnum.QUEUED.value,
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

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["currently_queued"], 1)
        self.assertFalse(data["safe_to_retry"])

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_no_notifications_returns_zeros(
        self, mock_authenticate, mock_require_current_user, mock_get_current_user
    ):
        """Test GET with no notifications returns all zeros."""
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["failed_retryable"], 0)
        self.assertEqual(data["failed_exhausted"], 0)
        self.assertEqual(data["currently_queued"], 0)
        self.assertTrue(data["safe_to_retry"])

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_excludes_sent_and_pending_notifications(
        self, mock_authenticate, mock_require_current_user, mock_get_current_user
    ):
        """Test GET only counts failed and queued notifications."""
        # Create notifications with different statuses
        self._create_notification_with_status(
            status=NotificationStatusEnum.SENT.value,
            retry_count=0,
        )
        self._create_notification_with_status(
            status=NotificationStatusEnum.PENDING.value,
            retry_count=0,
        )
        # Only this one should count
        self._create_notification_with_status(
            status=NotificationStatusEnum.FAILED.value,
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

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Only 1 failed notification should be counted
        self.assertEqual(data["failed_retryable"], 1)
        self.assertEqual(data["failed_exhausted"], 0)
        self.assertEqual(data["currently_queued"], 0)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_is_not_cached(
        self, mock_authenticate, mock_require_current_user, mock_get_current_user
    ):
        """Test GET returns fresh data (not cached)."""
        # Create initial failed notification
        self._create_notification_with_status(
            status=NotificationStatusEnum.FAILED.value,
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

        # First request
        response1 = self.client.get(self.url)
        data1 = response1.json()
        self.assertEqual(data1["failed_retryable"], 1)

        # Add another failed notification
        self._create_notification_with_status(
            status=NotificationStatusEnum.FAILED.value,
            retry_count=0,
        )

        # Second request should show updated count (not cached)
        response2 = self.client.get(self.url)
        data2 = response2.json()
        self.assertEqual(data2["failed_retryable"], 2)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_correctly_distinguishes_retry_count_thresholds(
        self, mock_authenticate, mock_require_current_user, mock_get_current_user
    ):
        """Test GET categorizes notifications by retry_count vs MAX_RETRIES."""
        # Retryable notifications have retry_count < MAX_RETRIES
        self._create_notification_with_status(
            status=NotificationStatusEnum.FAILED.value,
            retry_count=2,  # 2 < 3: retryable
        )
        self._create_notification_with_status(
            status=NotificationStatusEnum.FAILED.value,
            retry_count=1,  # 1 < 3: retryable
        )

        # Exhausted notifications have retry_count >= MAX_RETRIES
        self._create_notification_with_status(
            status=NotificationStatusEnum.FAILED.value,
            retry_count=3,  # 3 >= 3: exhausted
        )
        self._create_notification_with_status(
            status=NotificationStatusEnum.FAILED.value,
            retry_count=5,  # 5 >= 3: exhausted
        )

        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["failed_retryable"], 2)
        self.assertEqual(data["failed_exhausted"], 2)
