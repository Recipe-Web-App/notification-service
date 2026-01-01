"""Component tests for maintenance notification endpoint.

This module tests the /notifications/maintenance endpoint through the
full Django request/response cycle, including authentication, authorization,
and HTTP handling.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import Client, TestCase

from core.auth.oauth2 import OAuth2User


class TestMaintenanceEndpoint(TestCase):
    """Component tests for maintenance notification endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.url = "/api/v1/notification/notifications/maintenance"

        # Test data
        now = datetime.now(UTC)
        self.request_data = {
            "maintenance_start": (now + timedelta(hours=1)).isoformat(),
            "maintenance_end": (now + timedelta(hours=3)).isoformat(),
            "description": "Scheduled database maintenance",
            "admin_only": False,
        }

        # Mock user
        self.mock_user = Mock()
        self.mock_user.user_id = uuid4()
        self.mock_user.email = "user@example.com"
        self.mock_user.username = "testuser"
        self.mock_user.full_name = "Test User"

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.User")
    @patch("core.services.system_notification_service.notification_service")
    def test_post_with_admin_scope_returns_202(
        self,
        mock_notification_service,
        mock_user_model,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test POST with admin scope returns HTTP 202."""
        # Setup admin user
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup user query mock
        mock_queryset = Mock()
        mock_queryset.__iter__ = Mock(return_value=iter([self.mock_user]))
        mock_user_model.objects.filter.return_value = mock_queryset

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = (
            mock_notification,
            [],
        )

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
        # Setup non-admin user
        non_admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (non_admin_user, None)
        mock_get_current_user.return_value = non_admin_user

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
        # Setup admin user
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Invalid payload - missing maintenance_end
        invalid_data = {
            "maintenance_start": datetime.now(UTC).isoformat(),
            "description": "Test maintenance",
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
    def test_post_with_invalid_maintenance_window_returns_400(
        self, mock_authenticate, mock_get_current_user
    ):
        """Test POST where maintenance_end < maintenance_start returns HTTP 400."""
        # Setup admin user
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Invalid dates - end before start
        now = datetime.now(UTC)
        invalid_data = {
            "maintenance_start": (now + timedelta(hours=3)).isoformat(),
            "maintenance_end": (now + timedelta(hours=1)).isoformat(),
            "description": "Test maintenance",
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
    @patch("core.services.system_notification_service.User")
    @patch("core.services.system_notification_service.notification_service")
    def test_broadcast_to_all_users(
        self,
        mock_notification_service,
        mock_user_model,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test adminOnly=False broadcasts to all users."""
        # Setup admin user
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup multiple users
        user1 = Mock()
        user1.user_id = uuid4()
        user1.email = "user1@example.com"
        user1.username = "user1"
        user1.full_name = "User One"

        user2 = Mock()
        user2.user_id = uuid4()
        user2.email = "user2@example.com"
        user2.username = "user2"
        user2.full_name = "User Two"

        mock_queryset = Mock()
        mock_queryset.__iter__ = Mock(return_value=iter([user1, user2]))
        mock_user_model.objects.filter.return_value = mock_queryset

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = (
            mock_notification,
            [],
        )

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertEqual(data["queued_count"], 2)
        self.assertEqual(len(data["notifications"]), 2)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.User")
    @patch("core.services.system_notification_service.notification_service")
    def test_admin_only_broadcast(
        self,
        mock_notification_service,
        mock_user_model,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test adminOnly=True sends only to admins."""
        # Setup admin user
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup admin-only data
        admin_only_data = self.request_data.copy()
        admin_only_data["admin_only"] = True

        # Setup single admin user
        mock_queryset = Mock()
        mock_queryset.__iter__ = Mock(return_value=iter([self.mock_user]))
        mock_user_model.objects.filter.return_value = mock_queryset

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = (
            mock_notification,
            [],
        )

        # Execute
        response = self.client.post(
            self.url,
            data=admin_only_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertEqual(data["queued_count"], 1)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.system_notification_service.User")
    @patch("core.services.system_notification_service.notification_service")
    def test_response_contains_notification_ids(
        self,
        mock_notification_service,
        mock_user_model,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test response contains notification IDs and recipient IDs."""
        # Setup admin user
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup user query mock
        mock_queryset = Mock()
        mock_queryset.__iter__ = Mock(return_value=iter([self.mock_user]))
        mock_user_model.objects.filter.return_value = mock_queryset

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = (
            mock_notification,
            [],
        )

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
        for notification in data["notifications"]:
            self.assertIn("notification_id", notification)
            self.assertIn("recipient_id", notification)
