"""Component tests for notification detail endpoint.

This module tests the /notifications/{notificationId} endpoint through the
full Django request/response cycle, including authentication, authorization,
and HTTP handling.
"""

from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import Client, TestCase

from core.auth.oauth2 import OAuth2User
from core.models.notification import Notification


class TestNotificationDetailGetEndpoint(TestCase):
    """Component tests for GET /notifications/{notificationId}."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.notification_id = uuid4()
        self.user_id = uuid4()
        self.other_user_id = uuid4()
        self.url = f"/api/v1/notification/notifications/{self.notification_id}"

        # Mock notification
        self.mock_notification = Mock(spec=Notification)
        self.mock_notification.notification_id = self.notification_id
        self.mock_notification.recipient = Mock()
        self.mock_notification.recipient.user_id = self.user_id
        self.mock_notification.recipient_id = self.user_id
        self.mock_notification.recipient_email = "user@example.com"
        self.mock_notification.subject = "Test Notification"
        self.mock_notification.message = "This is a test message body"
        self.mock_notification.notification_type = "email"
        self.mock_notification.status = "sent"
        self.mock_notification.error_message = ""
        self.mock_notification.retry_count = 0
        self.mock_notification.max_retries = 3
        self.mock_notification.created_at = datetime.now(UTC)
        self.mock_notification.queued_at = datetime.now(UTC)
        self.mock_notification.sent_at = datetime.now(UTC)
        self.mock_notification.failed_at = None
        self.mock_notification.metadata = {"template_type": "recipe_published"}

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.Notification.objects.get")
    def test_get_as_admin_returns_200(
        self,
        mock_notification_get,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test GET with admin scope returns HTTP 200."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup notification mock
        mock_notification_get.return_value = self.mock_notification

        # Execute
        response = self.client.get(self.url)

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["notification_id"], str(self.notification_id))
        self.assertEqual(data["subject"], "Test Notification")
        self.assertNotIn("message", data)  # Message excluded by default

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.Notification.objects.get")
    def test_get_as_owner_returns_200(
        self,
        mock_notification_get,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test GET as notification owner returns HTTP 200."""
        # Setup authentication as owner
        owner_user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (owner_user, None)
        mock_get_current_user.return_value = owner_user

        # Setup notification mock
        mock_notification_get.return_value = self.mock_notification

        # Execute
        response = self.client.get(self.url)

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["notification_id"], str(self.notification_id))

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.Notification.objects.get")
    def test_get_with_include_message_returns_message(
        self,
        mock_notification_get,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test GET with include_message=true includes message body."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup notification mock
        mock_notification_get.return_value = self.mock_notification

        # Execute with include_message query param
        response = self.client.get(f"{self.url}?include_message=true")

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("message", data)
        self.assertEqual(data["message"], "This is a test message body")

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.Notification.objects.get")
    def test_get_as_non_owner_returns_403(
        self,
        mock_notification_get,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test GET as non-owner without admin scope returns HTTP 403."""
        # Setup authentication as different user
        other_user = OAuth2User(
            user_id=str(self.other_user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (other_user, None)
        mock_get_current_user.return_value = other_user

        # Setup notification mock
        mock_notification_get.return_value = self.mock_notification

        # Execute
        response = self.client.get(self.url)

        # Assertions
        self.assertEqual(response.status_code, 403)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.Notification.objects.get")
    def test_get_nonexistent_notification_returns_404(
        self,
        mock_notification_get,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test GET with non-existent notification returns HTTP 404."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup notification not found
        mock_notification_get.side_effect = Notification.DoesNotExist()

        # Execute
        response = self.client.get(self.url)

        # Assertions
        self.assertEqual(response.status_code, 404)

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_invalid_uuid_returns_400(self, mock_authenticate):
        """Test GET with invalid UUID format returns HTTP 400."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)

        # Execute with invalid UUID
        invalid_url = "/api/v1/notification/notifications/not-a-valid-uuid"
        response = self.client.get(invalid_url)

        # Assertions
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "bad_request")

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_unauthenticated_returns_401(self, mock_authenticate):
        """Test GET without authentication returns HTTP 401."""
        # Setup no authentication
        mock_authenticate.return_value = None

        # Execute
        response = self.client.get(self.url)

        # Assertions
        self.assertEqual(response.status_code, 401)


class TestNotificationDetailDeleteEndpoint(TestCase):
    """Component tests for DELETE /notifications/{notificationId}."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.notification_id = uuid4()
        self.user_id = uuid4()
        self.other_user_id = uuid4()
        self.url = f"/api/v1/notification/notifications/{self.notification_id}"

        # Mock notification
        self.mock_notification = Mock(spec=Notification)
        self.mock_notification.notification_id = self.notification_id
        self.mock_notification.recipient = Mock()
        self.mock_notification.recipient.user_id = self.user_id
        self.mock_notification.status = "sent"
        self.mock_notification.delete = Mock()

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.Notification.objects.get")
    def test_delete_as_admin_returns_204(
        self,
        mock_notification_get,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test DELETE with admin scope returns HTTP 204."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup notification mock
        mock_notification_get.return_value = self.mock_notification

        # Execute
        response = self.client.delete(self.url)

        # Assertions
        self.assertEqual(response.status_code, 204)
        self.mock_notification.delete.assert_called_once()

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.Notification.objects.get")
    def test_delete_as_owner_returns_204(
        self,
        mock_notification_get,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test DELETE as notification owner returns HTTP 204."""
        # Setup authentication as owner
        owner_user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (owner_user, None)
        mock_get_current_user.return_value = owner_user

        # Setup notification mock
        mock_notification_get.return_value = self.mock_notification

        # Execute
        response = self.client.delete(self.url)

        # Assertions
        self.assertEqual(response.status_code, 204)
        self.mock_notification.delete.assert_called_once()

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.Notification.objects.get")
    def test_delete_as_non_owner_returns_403(
        self,
        mock_notification_get,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test DELETE as non-owner without admin scope returns HTTP 403."""
        # Setup authentication as different user
        other_user = OAuth2User(
            user_id=str(self.other_user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (other_user, None)
        mock_get_current_user.return_value = other_user

        # Setup notification mock
        mock_notification_get.return_value = self.mock_notification

        # Execute
        response = self.client.delete(self.url)

        # Assertions
        self.assertEqual(response.status_code, 403)
        self.mock_notification.delete.assert_not_called()

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.Notification.objects.get")
    def test_delete_queued_notification_returns_409(
        self,
        mock_notification_get,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test DELETE with queued notification returns HTTP 409."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup queued notification
        queued_notification = Mock(spec=Notification)
        queued_notification.notification_id = self.notification_id
        queued_notification.recipient = Mock()
        queued_notification.recipient.user_id = self.user_id
        queued_notification.status = Notification.QUEUED
        mock_notification_get.return_value = queued_notification

        # Execute
        response = self.client.delete(self.url)

        # Assertions
        self.assertEqual(response.status_code, 409)
        data = response.json()
        self.assertEqual(data["error"], "conflict")
        queued_notification.delete.assert_not_called()

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.Notification.objects.get")
    def test_delete_nonexistent_notification_returns_404(
        self,
        mock_notification_get,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test DELETE with non-existent notification returns HTTP 404."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup notification not found
        mock_notification_get.side_effect = Notification.DoesNotExist()

        # Execute
        response = self.client.delete(self.url)

        # Assertions
        self.assertEqual(response.status_code, 404)

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_delete_invalid_uuid_returns_400(self, mock_authenticate):
        """Test DELETE with invalid UUID format returns HTTP 400."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)

        # Execute with invalid UUID
        invalid_url = "/api/v1/notification/notifications/not-a-valid-uuid"
        response = self.client.delete(invalid_url)

        # Assertions
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "bad_request")

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_delete_unauthenticated_returns_401(self, mock_authenticate):
        """Test DELETE without authentication returns HTTP 401."""
        # Setup no authentication
        mock_authenticate.return_value = None

        # Execute
        response = self.client.delete(self.url)

        # Assertions
        self.assertEqual(response.status_code, 401)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.Notification.objects.get")
    def test_delete_sent_notification_succeeds(
        self,
        mock_notification_get,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test DELETE with sent notification succeeds (only queued is blocked)."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup sent notification
        self.mock_notification.status = "sent"
        mock_notification_get.return_value = self.mock_notification

        # Execute
        response = self.client.delete(self.url)

        # Assertions
        self.assertEqual(response.status_code, 204)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.Notification.objects.get")
    def test_delete_failed_notification_succeeds(
        self,
        mock_notification_get,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test DELETE with failed notification succeeds (only queued is blocked)."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup failed notification
        self.mock_notification.status = "failed"
        mock_notification_get.return_value = self.mock_notification

        # Execute
        response = self.client.delete(self.url)

        # Assertions
        self.assertEqual(response.status_code, 204)
