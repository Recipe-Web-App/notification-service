"""Component tests for POST /notifications/{notification_id}/retry endpoint."""

import uuid
from unittest.mock import patch

from django.core.cache import cache
from django.db.models.signals import post_save
from django.test import TestCase, override_settings
from django.test.signals import setting_changed

from core.auth.oauth2 import OAuth2User
from core.enums.notification import NotificationStatusEnum, NotificationType
from core.models import Notification, NotificationStatus, User
from core.signals.user_signals import send_welcome_email

# Max retries constant (matches admin_service.MAX_RETRIES)
MAX_RETRIES = 3


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class RetryNotificationEndpointTestCase(TestCase):
    """Test cases for POST /notifications/{notification_id}/retry endpoint."""

    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        super().setUpClass()
        setting_changed.send(sender=cls, setting="CACHES", value={}, enter=True)

    def setUp(self):
        """Set up test fixtures."""
        # Clear cache before each test
        cache.clear()

        # Disconnect signals to avoid side effects
        post_save.disconnect(send_welcome_email, sender=User)

        # Create test user IDs
        self.admin_id = uuid.uuid4()
        self.user_id = uuid.uuid4()

        # Create test user
        self.user = User.objects.create(
            user_id=self.user_id,
            email="test@example.com",
            username="testuser",
            password_hash="test_hash",
        )

        # Create test notification ID
        self.notification_id = uuid.uuid4()

        # Define URL
        self.url = f"/api/v1/notification/notifications/{self.notification_id}/retry"

    def tearDown(self):
        """Clean up after each test."""
        # Clean up notifications and statuses
        NotificationStatus.objects.all().delete()
        Notification.objects.all().delete()
        post_save.connect(send_welcome_email, sender=User)
        cache.clear()

    def _create_notification_with_status(
        self,
        notification_id,
        status,
        retry_count=None,
        error_message=None,
    ):
        """Helper to create a notification with EMAIL status.

        Args:
            notification_id: UUID for the notification
            status: Status value for the NotificationStatus
            retry_count: Retry count for the status
            error_message: Error message for the status

        Returns:
            Tuple of (Notification, NotificationStatus)
        """
        notification = Notification.objects.create(
            notification_id=notification_id,
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
        """Test POST with admin scope successfully queues notification for retry."""
        # Setup admin user
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        # Create a failed notification with status
        _notification, email_status = self._create_notification_with_status(
            notification_id=self.notification_id,
            status=NotificationStatusEnum.FAILED.value,
            retry_count=1,
            error_message="Previous error",
        )

        # Execute
        response = self.client.post(self.url)

        # Assert response
        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertEqual(data["notification_id"], str(self.notification_id))
        self.assertEqual(data["status"], "queued")
        self.assertIn("retry", data["message"].lower())

        # Verify notification was queued
        mock_queue.assert_called_once_with(self.notification_id)

        # Verify error message was cleared on the status
        email_status.refresh_from_db()
        self.assertEqual(email_status.error_message, "")

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_without_admin_scope_returns_403(
        self, mock_authenticate, mock_get_current_user
    ):
        """Test POST without admin scope returns 403 Forbidden."""
        # Setup user with only user scope
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)
        mock_get_current_user.return_value = user

        # Execute
        response = self.client.post(self.url)

        # Assert
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertEqual(data["error"], "forbidden")
        self.assertIn("admin", data["detail"].lower())

    def test_post_unauthenticated_returns_401(self):
        """Test POST without authentication returns 401 Unauthorized."""
        # Execute
        response = self.client.post(self.url)

        # Assert
        self.assertEqual(response.status_code, 401)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_invalid_uuid_returns_400(
        self, mock_authenticate, mock_get_current_user
    ):
        """Test POST with invalid notification ID format returns 400."""
        # Setup admin user
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Execute with invalid UUID
        invalid_url = "/api/v1/notification/notifications/not-a-uuid/retry"
        response = self.client.post(invalid_url)

        # Assert
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "bad_request")
        self.assertIn("invalid", data["message"].lower())

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_nonexistent_notification_returns_404(
        self, mock_authenticate, mock_require_current_user, mock_get_current_user
    ):
        """Test POST with non-existent notification ID returns 404."""
        # Setup admin user
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        # Execute (notification doesn't exist)
        response = self.client.post(self.url)

        # Assert
        self.assertEqual(response.status_code, 404)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_sent_notification_returns_409(
        self, mock_authenticate, mock_require_current_user, mock_get_current_user
    ):
        """Test POST with notification in SENT status returns 409 Conflict."""
        # Setup admin user
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        # Create a SENT notification (cannot retry)
        self._create_notification_with_status(
            notification_id=self.notification_id,
            status=NotificationStatusEnum.SENT.value,
        )

        # Execute
        response = self.client.post(self.url)

        # Assert
        self.assertEqual(response.status_code, 409)
        data = response.json()
        self.assertEqual(data["error"], "conflict")
        self.assertIn("failed", data["message"].lower())
        self.assertIn("sent", data["detail"].lower())

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_exhausted_retries_returns_409(
        self, mock_authenticate, mock_require_current_user, mock_get_current_user
    ):
        """Test POST with exhausted retry count returns 409 Conflict."""
        # Setup admin user
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        # Create a failed notification with exhausted retries
        self._create_notification_with_status(
            notification_id=self.notification_id,
            status=NotificationStatusEnum.FAILED.value,
            retry_count=MAX_RETRIES,  # At max retries
            error_message="Max retries exceeded",
        )

        # Execute
        response = self.client.post(self.url)

        # Assert
        self.assertEqual(response.status_code, 409)
        data = response.json()
        self.assertEqual(data["error"], "conflict")
        self.assertIn("retry", data["message"].lower())
        self.assertIn("exhausted", data["message"].lower())

    @patch("core.services.notification_service.notification_service.queue_notification")
    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_clears_error_message_and_queues(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
        mock_queue,
    ):
        """Test POST clears error message before queuing notification."""
        # Setup admin user
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        # Create a failed notification with error message
        _notification, email_status = self._create_notification_with_status(
            notification_id=self.notification_id,
            status=NotificationStatusEnum.FAILED.value,
            retry_count=0,
            error_message="SMTP connection failed",
        )

        # Verify initial state
        self.assertEqual(email_status.error_message, "SMTP connection failed")

        # Execute
        response = self.client.post(self.url)

        # Assert response
        self.assertEqual(response.status_code, 202)

        # Verify error message was cleared on the status
        email_status.refresh_from_db()
        self.assertEqual(email_status.error_message, "")

        # Verify queue was called
        mock_queue.assert_called_once_with(self.notification_id)
