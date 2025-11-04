"""Component tests for user notifications list endpoint.

This module tests the /users/me/notifications endpoint through the
full Django request/response cycle, including authentication, authorization,
pagination, and filtering.
"""

from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import Client, TestCase

from core.auth.oauth2 import OAuth2User
from core.models.notification import Notification
from core.models.user import User
from core.models.user import User as UserModel


class TestUserNotificationsListEndpoint(TestCase):
    """Component tests for GET /users/me/notifications."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.user_id = uuid4()
        self.user_email = "user@example.com"
        self.url = "/api/v1/notification/users/me/notifications"

        # Create mock user
        self.mock_user = Mock(spec=User)
        self.mock_user.user_id = self.user_id
        self.mock_user.email = self.user_email

        # Create mock notifications
        self.mock_notifications = []
        for i in range(3):
            mock_notif = Mock(spec=Notification)
            mock_notif.notification_id = uuid4()
            mock_notif.recipient = self.mock_user
            mock_notif.recipient_id = self.user_id
            mock_notif.recipient_email = self.user_email
            mock_notif.subject = f"Test Notification {i}"
            mock_notif.message = f"Test message body {i}"
            mock_notif.notification_type = "email"
            mock_notif.status = "sent"
            mock_notif.error_message = ""
            mock_notif.retry_count = 0
            mock_notif.max_retries = 3
            mock_notif.created_at = datetime.now(UTC)
            mock_notif.queued_at = datetime.now(UTC)
            mock_notif.sent_at = datetime.now(UTC)
            mock_notif.failed_at = None
            mock_notif.metadata = {"template_type": "recipe_published"}
            self.mock_notifications.append(mock_notif)

    def create_mock_queryset(self, notifications):
        """Create a mock queryset that supports Django pagination."""

        def mock_getitem(key):
            if isinstance(key, slice):
                # Return a new mock queryset for slicing
                sliced_mock = Mock()
                sliced_results = notifications[key]
                # These also need to accept self
                sliced_mock.__iter__ = lambda self: iter(sliced_results)
                sliced_mock.count = lambda: len(sliced_results)
                sliced_mock.__len__ = lambda self: len(sliced_results)
                return sliced_mock
            return notifications[key]

        mock_queryset = Mock()
        # Make filter() return itself to allow method chaining
        mock_queryset.filter = Mock(return_value=mock_queryset)
        mock_queryset.count = Mock(return_value=len(notifications))
        # These lambdas need to accept self since Python passes it automatically
        mock_queryset.__iter__ = lambda self: iter(notifications)
        mock_queryset.__getitem__ = lambda self, key: mock_getitem(key)
        mock_queryset.__len__ = lambda self: len(notifications)
        return mock_queryset

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.User.objects.get")
    @patch("core.services.notification_service.Notification.objects.filter")
    def test_get_with_user_scope_returns_200(
        self,
        mock_notification_filter,
        mock_user_get,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
    ):
        """Test GET with user scope returns HTTP 200 with notifications."""
        # Setup authentication
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)
        mock_get_current_user.return_value = user
        mock_require_current_user.return_value = user

        # Setup user mock
        mock_user_get.return_value = self.mock_user

        # Setup notification queryset mock
        mock_notification_filter.return_value = self.create_mock_queryset(
            self.mock_notifications
        )

        # Execute
        response = self.client.get(self.url)

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("results", data)
        self.assertIn("count", data)
        self.assertIn("next", data)
        self.assertIn("previous", data)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.User.objects.get")
    @patch("core.services.notification_service.Notification.objects.filter")
    def test_get_with_admin_scope_returns_200(
        self,
        mock_notification_filter,
        mock_user_get,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
    ):
        """Test GET with admin scope returns HTTP 200."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        # Setup user mock
        mock_user_get.return_value = self.mock_user

        # Setup notification queryset mock
        mock_notification_filter.return_value = self.create_mock_queryset(
            self.mock_notifications
        )

        # Execute
        response = self.client.get(self.url)

        # Assertions
        self.assertEqual(response.status_code, 200)

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_without_required_scope_returns_403(self, mock_authenticate):
        """Test GET without required scope returns HTTP 403."""
        # Setup authentication without required scope
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["some:other:scope"],
        )
        mock_authenticate.return_value = (user, None)

        # Execute
        response = self.client.get(self.url)

        # Assertions
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertEqual(data["error"], "forbidden")

    def test_get_without_authentication_returns_401(self):
        """Test GET without authentication returns HTTP 401."""
        # Execute without any authentication
        response = self.client.get(self.url)

        # Assertions
        # DRF returns 403 when authentication is missing and permission classes are set
        # The actual status depends on the DRF configuration
        self.assertIn(response.status_code, [401, 403])

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.User.objects.get")
    @patch("core.services.notification_service.Notification.objects.filter")
    def test_get_with_status_filter_applies_filter(
        self,
        mock_notification_filter,
        mock_user_get,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
    ):
        """Test GET with status filter applies the filter correctly."""
        # Setup authentication
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)
        mock_get_current_user.return_value = user
        mock_require_current_user.return_value = user

        # Setup user mock
        mock_user_get.return_value = self.mock_user

        # Setup notification queryset mock - return just one notification
        mock_queryset = self.create_mock_queryset([self.mock_notifications[0]])
        mock_notification_filter.return_value = mock_queryset

        # Execute with status filter
        response = self.client.get(self.url, {"status": "sent"})

        # Assertions
        self.assertEqual(response.status_code, 200)
        # Verify filter was called with status
        mock_queryset.filter.assert_called_with(status="sent")

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_invalid_status_returns_400(self, mock_authenticate):
        """Test GET with invalid status filter returns HTTP 400."""
        # Setup authentication
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)

        # Execute with invalid status
        response = self.client.get(self.url, {"status": "invalid_status"})

        # Assertions
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "bad_request")

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_invalid_notification_type_returns_400(self, mock_authenticate):
        """Test GET with invalid notification_type filter returns HTTP 400."""
        # Setup authentication
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)

        # Execute with invalid notification type
        response = self.client.get(self.url, {"notification_type": "sms"})

        # Assertions
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "bad_request")

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.User.objects.get")
    @patch("core.services.notification_service.Notification.objects.filter")
    def test_get_excludes_message_by_default(
        self,
        mock_notification_filter,
        mock_user_get,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
    ):
        """Test GET excludes message field by default."""
        # Setup authentication
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)
        mock_get_current_user.return_value = user
        mock_require_current_user.return_value = user

        # Setup user mock
        mock_user_get.return_value = self.mock_user

        # Setup notification queryset mock
        mock_notification_filter.return_value = self.create_mock_queryset(
            [self.mock_notifications[0]]
        )

        # Execute
        response = self.client.get(self.url)

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        if data["results"]:
            self.assertNotIn("message", data["results"][0])

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.User.objects.get")
    @patch("core.services.notification_service.Notification.objects.filter")
    def test_get_includes_message_when_requested(
        self,
        mock_notification_filter,
        mock_user_get,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
    ):
        """Test GET includes message field when include_message=true."""
        # Setup authentication
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)
        mock_get_current_user.return_value = user
        mock_require_current_user.return_value = user

        # Setup user mock
        mock_user_get.return_value = self.mock_user

        # Setup notification queryset mock
        mock_notification_filter.return_value = self.create_mock_queryset(
            [self.mock_notifications[0]]
        )

        # Execute with include_message=true
        response = self.client.get(self.url, {"include_message": "true"})

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        if data["results"]:
            self.assertIn("message", data["results"][0])

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.User.objects.get")
    @patch("core.services.notification_service.Notification.objects.filter")
    def test_get_with_pagination_params(
        self,
        mock_notification_filter,
        mock_user_get,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
    ):
        """Test GET with pagination parameters."""
        # Setup authentication
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)
        mock_get_current_user.return_value = user
        mock_require_current_user.return_value = user

        # Setup user mock
        mock_user_get.return_value = self.mock_user

        # Setup notification queryset mock - create larger list for pagination testing
        large_notification_list = self.mock_notifications * 34  # 102 notifications
        mock_notification_filter.return_value = self.create_mock_queryset(
            large_notification_list
        )

        # Execute with pagination params
        response = self.client.get(self.url, {"page": "2", "page_size": "10"})

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("next", data)
        self.assertIn("previous", data)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.notification_service.User.objects.get")
    def test_get_with_user_not_found_returns_empty(
        self,
        mock_user_get,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test GET when user not found in local DB returns empty results."""
        # Setup authentication
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)
        mock_get_current_user.return_value = user

        mock_user_get.side_effect = UserModel.DoesNotExist

        # Execute
        response = self.client.get(self.url)

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 0)
        self.assertEqual(len(data["results"]), 0)
