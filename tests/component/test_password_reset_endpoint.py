"""Component tests for password-reset notification endpoint.

This module tests the /notifications/password-reset endpoint through the
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


class TestPasswordResetEndpoint(TestCase):
    """Component tests for password reset notification endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.url = "/api/v1/notification/notifications/password-reset"

        # Test data
        self.recipient_id = uuid4()
        self.reset_token = "secure_reset_token_123456789"
        self.expiry_hours = 24

        self.request_data = {
            "recipient_ids": [str(self.recipient_id)],
            "reset_token": self.reset_token,
            "expiry_hours": self.expiry_hours,
        }

        # Mock recipient user
        self.mock_recipient = UserSearchResult(
            user_id=self.recipient_id,
            username="testuser",
            email="testuser@example.com",
            full_name="Test User",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.user_client")
    @patch("core.services.system_notification_service.notification_service")
    def test_post_with_admin_scope_returns_202(
        self,
        mock_notification_service,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test POST with admin scope returns HTTP 202."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup service mocks
        mock_user_client.get_user.return_value = self.mock_recipient

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
    def test_post_without_admin_scope_returns_403(
        self, mock_authenticate, mock_get_current_user
    ):
        """Test POST without admin scope returns HTTP 403."""
        # Setup authentication with wrong scope
        user_without_admin = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user_without_admin, None)
        mock_get_current_user.return_value = user_without_admin

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertIn("notification:admin", data["detail"])

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_invalid_payload_returns_400(
        self, mock_authenticate, mock_get_current_user
    ):
        """Test POST with invalid payload returns HTTP 400."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Invalid payload - missing required field
        invalid_data = {
            "recipient_ids": [str(uuid4())],
            # Missing reset_token and expiry_hours
        }

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
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Invalid payload - empty recipient_ids
        invalid_data = {
            "recipient_ids": [],
            "reset_token": self.reset_token,
            "expiry_hours": 24,
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
    def test_post_with_multiple_recipients_returns_400(
        self, mock_authenticate, mock_get_current_user
    ):
        """Test POST with >1 recipient returns HTTP 400."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Invalid payload - multiple recipients (only 1 allowed)
        invalid_data = {
            "recipient_ids": [str(uuid4()), str(uuid4())],
            "reset_token": self.reset_token,
            "expiry_hours": 24,
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
    def test_post_with_short_reset_token_returns_400(
        self, mock_authenticate, mock_get_current_user
    ):
        """Test POST with reset token <20 chars returns HTTP 400."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Invalid payload - token too short
        invalid_data = {
            "recipient_ids": [str(self.recipient_id)],
            "reset_token": "short",  # Less than 20 characters
            "expiry_hours": 24,
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
    def test_post_with_invalid_expiry_hours_returns_400(
        self, mock_authenticate, mock_get_current_user
    ):
        """Test POST with expiry_hours outside 1-72 range returns HTTP 400."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Test expiry_hours = 0 (below minimum)
        invalid_data = {
            "recipient_ids": [str(self.recipient_id)],
            "reset_token": self.reset_token,
            "expiry_hours": 0,
        }

        response = self.client.post(
            self.url,
            data=invalid_data,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

        # Test expiry_hours = 73 (above maximum)
        invalid_data["expiry_hours"] = 73
        response = self.client.post(
            self.url,
            data=invalid_data,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.user_client")
    def test_post_with_nonexistent_user_returns_404(
        self, mock_user_client, mock_authenticate, mock_get_current_user
    ):
        """Test POST with nonexistent user returns HTTP 404."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

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
    def test_response_contains_notification_id(
        self,
        mock_notification_service,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test response contains notification ID and recipient ID."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup service mocks
        mock_user_client.get_user.return_value = self.mock_recipient

        notification_id = uuid4()
        mock_notification = Mock(notification_id=notification_id)
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
        self.assertEqual(len(data["notifications"]), 1)

        # Verify notification has ID and recipient_id
        notification = data["notifications"][0]
        self.assertIn("notification_id", notification)
        self.assertIn("recipient_id", notification)
        self.assertEqual(notification["notification_id"], str(notification_id))
        self.assertEqual(notification["recipient_id"], str(self.recipient_id))

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.user_client")
    @patch("core.services.system_notification_service.notification_service")
    @patch(
        "core.services.system_notification_service.FRONTEND_BASE_URL",
        "https://example.com",
    )
    def test_reset_url_constructed_correctly(
        self,
        mock_notification_service,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test that reset URL is constructed with correct token."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup service mocks
        mock_user_client.get_user.return_value = self.mock_recipient

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

        # Verify notification service was called with correct template data
        mock_notification_service.create_notification.assert_called_once()
        call_kwargs = mock_notification_service.create_notification.call_args[1]

        # Check that the message contains the reset token
        message = call_kwargs["message"]
        self.assertIn(self.reset_token, message)
        self.assertIn("https://example.com/reset-password?token=", message)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.user_client")
    @patch("core.services.system_notification_service.notification_service")
    def test_notification_includes_metadata(
        self,
        mock_notification_service,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test that notification includes correct metadata."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup service mocks
        mock_user_client.get_user.return_value = self.mock_recipient

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

        # Verify metadata
        mock_notification_service.create_notification.assert_called_once()
        call_kwargs = mock_notification_service.create_notification.call_args[1]

        metadata = call_kwargs["metadata"]
        self.assertEqual(metadata["template_type"], "password_reset")
        self.assertEqual(metadata["recipient_id"], str(self.recipient_id))
        self.assertEqual(metadata["expiry_hours"], self.expiry_hours)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.user_client")
    @patch("core.services.system_notification_service.notification_service")
    def test_notification_auto_queued(
        self,
        mock_notification_service,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test that notification is auto-queued for async processing."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup service mocks
        mock_user_client.get_user.return_value = self.mock_recipient

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

        # Verify auto_queue was set to True
        mock_notification_service.create_notification.assert_called_once()
        call_kwargs = mock_notification_service.create_notification.call_args[1]
        self.assertTrue(call_kwargs["auto_queue"])
