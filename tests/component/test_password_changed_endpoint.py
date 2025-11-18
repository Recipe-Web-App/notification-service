"""Component tests for password-changed notification endpoint.

This module tests the /notifications/password-changed endpoint through the
full Django request/response cycle, including authentication, authorization,
and HTTP handling.
"""

from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import Client, TestCase

from core.auth.oauth2 import OAuth2User
from core.exceptions import UserNotFoundError
from core.schemas.user import UserSearchResult


class TestPasswordChangedEndpoint(TestCase):
    """Component tests for password changed notification endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.url = "/api/v1/notification/notifications/password-changed"

        # Test data
        self.recipient_id = uuid4()

        self.request_data = {
            "recipient_ids": [str(self.recipient_id)],
        }

        # Mock user
        self.mock_user = UserSearchResult(
            user_id=self.recipient_id,
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.user_client")
    @patch("core.services.system_notification_service.notification_service")
    @patch("core.services.system_notification_service.render_to_string")
    def test_post_with_service_to_service_auth_returns_202(
        self,
        mock_render,
        mock_notification_service,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test POST with service-to-service auth returns HTTP 202."""
        # Setup service-to-service authentication (user_id == client_id)
        service_user_id = str(uuid4())
        service_user = OAuth2User(
            user_id=service_user_id,
            client_id=service_user_id,  # Same as user_id for service-to-service
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (service_user, None)
        mock_get_current_user.return_value = service_user

        # Setup service mocks
        mock_user_client.get_user.return_value = self.mock_user
        mock_render.return_value = "<html>email content</html>"

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 202)

        data = response.json()
        self.assertEqual(data["queued_count"], 1)
        self.assertEqual(len(data["notifications"]), 1)
        self.assertEqual(data["message"], "Notifications queued successfully")

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_without_authentication_returns_401(
        self, mock_authenticate, mock_get_current_user
    ):
        """Test POST without authentication returns HTTP 401."""
        # Setup authentication to fail
        mock_authenticate.return_value = None

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 401)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_without_service_to_service_auth_returns_403(
        self, mock_authenticate, mock_get_current_user
    ):
        """Test POST without service-to-service auth returns HTTP 403."""
        # Setup non-service authentication (user_id != client_id)
        non_service_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="different-client-id",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (non_service_user, None)
        mock_get_current_user.return_value = non_service_user

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertIn("service-to-service authentication", data["detail"])

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_invalid_payload_returns_400(
        self, mock_authenticate, mock_get_current_user
    ):
        """Test POST with invalid payload returns HTTP 400."""
        # Setup service-to-service authentication
        service_user_id = str(uuid4())
        service_user = OAuth2User(
            user_id=service_user_id,
            client_id=service_user_id,
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (service_user, None)
        mock_get_current_user.return_value = service_user

        # Invalid payload - missing recipient_ids
        invalid_data = {}

        # Execute
        response = self.client.post(
            self.url,
            data=invalid_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "bad_request")
        self.assertIn("errors", data)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_empty_recipient_list_returns_400(
        self, mock_authenticate, mock_get_current_user
    ):
        """Test POST with empty recipient list returns HTTP 400."""
        # Setup service-to-service authentication
        service_user_id = str(uuid4())
        service_user = OAuth2User(
            user_id=service_user_id,
            client_id=service_user_id,
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (service_user, None)
        mock_get_current_user.return_value = service_user

        # Invalid payload - empty recipient_ids
        invalid_data = {
            "recipient_ids": [],
        }

        # Execute
        response = self.client.post(
            self.url,
            data=invalid_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 400)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.user_client")
    def test_post_with_nonexistent_user_returns_404(
        self, mock_user_client, mock_authenticate, mock_get_current_user
    ):
        """Test POST with nonexistent user returns HTTP 404."""
        # Setup service-to-service authentication
        service_user_id = str(uuid4())
        service_user = OAuth2User(
            user_id=service_user_id,
            client_id=service_user_id,
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (service_user, None)
        mock_get_current_user.return_value = service_user

        # Setup user client to raise UserNotFoundError
        mock_user_client.get_user.side_effect = UserNotFoundError(
            user_id=str(self.recipient_id)
        )

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 404)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.user_client")
    @patch("core.services.system_notification_service.notification_service")
    @patch("core.services.system_notification_service.render_to_string")
    def test_response_contains_notification_id(
        self,
        mock_render,
        mock_notification_service,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test response contains notification ID and recipient ID."""
        # Setup service-to-service authentication
        service_user_id = str(uuid4())
        service_user = OAuth2User(
            user_id=service_user_id,
            client_id=service_user_id,
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (service_user, None)
        mock_get_current_user.return_value = service_user

        # Setup service mocks
        mock_user_client.get_user.return_value = self.mock_user
        mock_render.return_value = "<html>email content</html>"

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertIn("notifications", data)
        self.assertIn("queued_count", data)
        self.assertIn("message", data)
        self.assertEqual(len(data["notifications"]), 1)
        self.assertEqual(data["queued_count"], 1)
        for notification in data["notifications"]:
            self.assertIn("notification_id", notification)
            self.assertIn("recipient_id", notification)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.user_client")
    @patch("core.services.system_notification_service.notification_service")
    @patch("core.services.system_notification_service.render_to_string")
    def test_batch_processing_multiple_recipients(
        self,
        mock_render,
        mock_notification_service,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test batch processing creates one notification per recipient."""
        # Setup service-to-service authentication
        service_user_id = str(uuid4())
        service_user = OAuth2User(
            user_id=service_user_id,
            client_id=service_user_id,
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (service_user, None)
        mock_get_current_user.return_value = service_user

        # Setup service mocks
        mock_user_client.get_user.return_value = self.mock_user
        mock_render.return_value = "<html>email content</html>"

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Create request with 3 recipients
        batch_data = {
            "recipient_ids": [str(uuid4()), str(uuid4()), str(uuid4())],
        }

        # Execute
        response = self.client.post(
            self.url,
            data=batch_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertEqual(data["queued_count"], 3)
        self.assertEqual(len(data["notifications"]), 3)
