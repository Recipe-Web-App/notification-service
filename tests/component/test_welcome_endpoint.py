"""Component tests for welcome notification endpoint.

This module tests the /notifications/welcome endpoint through the
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


class TestWelcomeEndpoint(TestCase):
    """Component tests for welcome notification endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.url = "/api/v1/notification/notifications/welcome"

        # Test data
        self.recipient_id_1 = uuid4()
        self.recipient_id_2 = uuid4()

        self.request_data_single = {
            "recipient_ids": [str(self.recipient_id_1)],
        }

        self.request_data_batch = {
            "recipient_ids": [str(self.recipient_id_1), str(self.recipient_id_2)],
        }

        # Mock recipient users
        self.mock_recipient_1 = UserSearchResult(
            user_id=self.recipient_id_1,
            username="testuser1",
            email="testuser1@example.com",
            full_name="Test User One",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        self.mock_recipient_2 = UserSearchResult(
            user_id=self.recipient_id_2,
            username="testuser2",
            email="testuser2@example.com",
            full_name=None,  # Test fallback to username
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.user_client")
    @patch("core.services.system_notification_service.notification_service")
    @patch("core.services.system_notification_service.User.objects")
    def test_post_with_service_to_service_auth_returns_202(
        self,
        mock_user_objects,
        mock_notification_service,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test POST with service-to-service auth returns HTTP 202."""
        # Setup service-to-service authentication
        # For client_credentials grant, user_id equals client_id
        service_user = OAuth2User(
            user_id="user-management-service",
            client_id="user-management-service",
            scopes=["notification:write"],
        )
        mock_authenticate.return_value = (service_user, None)
        mock_get_current_user.return_value = service_user

        # Setup service mocks
        mock_user_client.get_user.return_value = self.mock_recipient_1

        mock_db_user = Mock()
        mock_db_user.user_id = self.recipient_id_1
        mock_user_objects.get.return_value = mock_db_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = (
            mock_notification,
            [],
        )

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data_single,
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
    @patch("core.services.system_notification_service.user_client")
    @patch("core.services.system_notification_service.notification_service")
    @patch("core.services.system_notification_service.User.objects")
    def test_post_with_batch_recipients_returns_202(
        self,
        mock_user_objects,
        mock_notification_service,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test POST with multiple recipients returns HTTP 202."""
        # Setup service-to-service authentication
        service_user = OAuth2User(
            user_id="user-management-service",
            client_id="user-management-service",
            scopes=["notification:write"],
        )
        mock_authenticate.return_value = (service_user, None)
        mock_get_current_user.return_value = service_user

        # Setup service mocks to return different users
        def get_user_side_effect(user_id):
            if user_id == str(self.recipient_id_1):
                return self.mock_recipient_1
            return self.mock_recipient_2

        mock_user_client.get_user.side_effect = get_user_side_effect

        mock_db_user = Mock()
        mock_user_objects.get.return_value = mock_db_user

        mock_notification_1 = Mock(notification_id=uuid4())
        mock_notification_2 = Mock(notification_id=uuid4())
        mock_notification_service.create_notification.side_effect = [
            (mock_notification_1, []),
            (mock_notification_2, []),
        ]

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data_batch,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 202)

        data = response.json()
        self.assertEqual(data["queued_count"], 2)
        self.assertEqual(len(data["notifications"]), 2)
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
            data=self.request_data_single,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 401)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_user_auth_returns_403(
        self, mock_authenticate, mock_get_current_user
    ):
        """Test POST with user auth (non-service) returns HTTP 403."""
        # Setup authentication with user context (user_id != client_id)
        user_auth = OAuth2User(
            user_id=str(uuid4()),  # Different from client_id
            client_id="web-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user_auth, None)
        mock_get_current_user.return_value = user_auth

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data_single,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertIn("service-to-service", data["detail"])

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_invalid_payload_returns_400(
        self, mock_authenticate, mock_get_current_user
    ):
        """Test POST with invalid payload returns HTTP 400."""
        # Setup service authentication
        service_user = OAuth2User(
            user_id="user-management-service",
            client_id="user-management-service",
            scopes=["notification:write"],
        )
        mock_authenticate.return_value = (service_user, None)
        mock_get_current_user.return_value = service_user

        # Invalid payload - missing required field
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
        # Setup service authentication
        service_user = OAuth2User(
            user_id="user-management-service",
            client_id="user-management-service",
            scopes=["notification:write"],
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
        # Setup service authentication
        service_user = OAuth2User(
            user_id="user-management-service",
            client_id="user-management-service",
            scopes=["notification:write"],
        )
        mock_authenticate.return_value = (service_user, None)
        mock_get_current_user.return_value = service_user

        # Setup user client to raise UserNotFoundError
        mock_user_client.get_user.side_effect = UserNotFoundError(
            user_id=str(self.recipient_id_1)
        )

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data_single,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 404)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.user_client")
    @patch("core.services.system_notification_service.notification_service")
    @patch("core.services.system_notification_service.User.objects")
    def test_response_contains_notification_ids(
        self,
        mock_user_objects,
        mock_notification_service,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test response contains notification IDs and recipient IDs."""
        # Setup service authentication
        service_user = OAuth2User(
            user_id="user-management-service",
            client_id="user-management-service",
            scopes=["notification:write"],
        )
        mock_authenticate.return_value = (service_user, None)
        mock_get_current_user.return_value = service_user

        # Setup service mocks
        mock_user_client.get_user.return_value = self.mock_recipient_1

        mock_db_user = Mock()
        mock_db_user.user_id = self.recipient_id_1
        mock_user_objects.get.return_value = mock_db_user

        notification_id = uuid4()
        mock_notification = Mock(notification_id=notification_id)
        mock_notification_service.create_notification.return_value = (
            mock_notification,
            [],
        )

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data_single,
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
        self.assertEqual(notification["recipient_id"], str(self.recipient_id_1))

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.user_client")
    @patch("core.services.system_notification_service.notification_service")
    @patch("core.services.system_notification_service.User.objects")
    @patch(
        "core.services.system_notification_service.FRONTEND_BASE_URL",
        "https://example.com",
    )
    def test_welcome_notification_uses_full_name(
        self,
        mock_user_objects,
        mock_notification_service,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test that welcome notification uses full name when available."""
        # Setup service authentication
        service_user = OAuth2User(
            user_id="user-management-service",
            client_id="user-management-service",
            scopes=["notification:write"],
        )
        mock_authenticate.return_value = (service_user, None)
        mock_get_current_user.return_value = service_user

        # Setup service mocks with user that has full_name
        mock_user_client.get_user.return_value = self.mock_recipient_1

        mock_db_user = Mock()
        mock_db_user.user_id = self.recipient_id_1
        mock_user_objects.get.return_value = mock_db_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = (
            mock_notification,
            [],
        )

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data_single,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 202)

        # Verify notification service was called with correct template data
        mock_notification_service.create_notification.assert_called_once()
        call_kwargs = mock_notification_service.create_notification.call_args[1]

        # Check that notification_data contains the full name
        notification_data = call_kwargs["notification_data"]
        self.assertEqual(notification_data["username"], "Test User One")
        self.assertEqual(notification_data["recipient_name"], "Test User One")

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.user_client")
    @patch("core.services.system_notification_service.notification_service")
    @patch("core.services.system_notification_service.User.objects")
    @patch(
        "core.services.system_notification_service.FRONTEND_BASE_URL",
        "https://example.com",
    )
    def test_welcome_notification_falls_back_to_username(
        self,
        mock_user_objects,
        mock_notification_service,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test welcome notification falls back to username when full_name is None."""
        # Setup service authentication
        service_user = OAuth2User(
            user_id="user-management-service",
            client_id="user-management-service",
            scopes=["notification:write"],
        )
        mock_authenticate.return_value = (service_user, None)
        mock_get_current_user.return_value = service_user

        # Setup service mocks with user that has no full_name
        mock_user_client.get_user.return_value = self.mock_recipient_2

        mock_db_user = Mock()
        mock_db_user.user_id = self.recipient_id_2
        mock_user_objects.get.return_value = mock_db_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = (
            mock_notification,
            [],
        )

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data_single,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 202)

        # Verify notification service was called with correct template data
        mock_notification_service.create_notification.assert_called_once()
        call_kwargs = mock_notification_service.create_notification.call_args[1]

        # Check that notification_data contains the username (fallback)
        notification_data = call_kwargs["notification_data"]
        self.assertEqual(notification_data["username"], "testuser2")
        self.assertEqual(notification_data["recipient_name"], "testuser2")

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.user_client")
    @patch("core.services.system_notification_service.notification_service")
    @patch("core.services.system_notification_service.User.objects")
    def test_notification_includes_notification_data(
        self,
        mock_user_objects,
        mock_notification_service,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test that notification includes correct notification_data."""
        # Setup service authentication
        service_user = OAuth2User(
            user_id="user-management-service",
            client_id="user-management-service",
            scopes=["notification:write"],
        )
        mock_authenticate.return_value = (service_user, None)
        mock_get_current_user.return_value = service_user

        # Setup service mocks
        mock_user_client.get_user.return_value = self.mock_recipient_1

        mock_db_user = Mock()
        mock_db_user.user_id = self.recipient_id_1
        mock_user_objects.get.return_value = mock_db_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = (
            mock_notification,
            [],
        )

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data_single,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 202)

        # Verify notification_data
        mock_notification_service.create_notification.assert_called_once()
        call_kwargs = mock_notification_service.create_notification.call_args[1]

        notification_data = call_kwargs["notification_data"]
        self.assertEqual(notification_data["template_version"], "1.0")
        self.assertEqual(notification_data["recipient_id"], str(self.recipient_id_1))
        self.assertIn("app_url", notification_data)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.user_client")
    @patch("core.services.system_notification_service.notification_service")
    @patch("core.services.system_notification_service.User.objects")
    def test_notification_uses_correct_category(
        self,
        mock_user_objects,
        mock_notification_service,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test that notification uses correct category."""
        # Setup service authentication
        service_user = OAuth2User(
            user_id="user-management-service",
            client_id="user-management-service",
            scopes=["notification:write"],
        )
        mock_authenticate.return_value = (service_user, None)
        mock_get_current_user.return_value = service_user

        # Setup service mocks
        mock_user_client.get_user.return_value = self.mock_recipient_1

        mock_db_user = Mock()
        mock_db_user.user_id = self.recipient_id_1
        mock_user_objects.get.return_value = mock_db_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = (
            mock_notification,
            [],
        )

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data_single,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 202)

        # Verify category
        mock_notification_service.create_notification.assert_called_once()
        call_kwargs = mock_notification_service.create_notification.call_args[1]
        self.assertEqual(call_kwargs["notification_category"], "WELCOME")

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.user_client")
    @patch("core.services.system_notification_service.notification_service")
    @patch("core.services.system_notification_service.User.objects")
    def test_notification_includes_recipient_email(
        self,
        mock_user_objects,
        mock_notification_service,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test that notification includes recipient email."""
        # Setup service authentication
        service_user = OAuth2User(
            user_id="user-management-service",
            client_id="user-management-service",
            scopes=["notification:write"],
        )
        mock_authenticate.return_value = (service_user, None)
        mock_get_current_user.return_value = service_user

        # Setup service mocks
        mock_user_client.get_user.return_value = self.mock_recipient_1

        mock_db_user = Mock()
        mock_db_user.user_id = self.recipient_id_1
        mock_user_objects.get.return_value = mock_db_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = (
            mock_notification,
            [],
        )

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data_single,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 202)

        # Verify recipient_email
        mock_notification_service.create_notification.assert_called_once()
        call_kwargs = mock_notification_service.create_notification.call_args[1]
        self.assertEqual(call_kwargs["recipient_email"], "testuser1@example.com")
