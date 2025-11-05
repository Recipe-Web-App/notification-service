"""Component tests for user notifications list endpoint.

This module tests the /users/me/notifications endpoint through the
full Django request/response cycle, including authentication, authorization,
pagination, and filtering.
"""

from unittest.mock import patch
from uuid import uuid4

from django.db.models.signals import post_save
from django.test import Client, TestCase

from core.auth.oauth2 import OAuth2User
from core.models.notification import Notification
from core.models.user import User
from core.signals.user_signals import send_welcome_email


class TestUserNotificationsListEndpoint(TestCase):
    """Component tests for GET /users/me/notifications."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.user_id = uuid4()
        self.user_email = "user@example.com"
        self.url = "/api/v1/notification/users/me/notifications"

        post_save.disconnect(send_welcome_email, sender=User)

        # Create REAL user in test database
        self.user = User.objects.create(
            user_id=self.user_id,
            email=self.user_email,
            username="testuser",
            password_hash="test_hash",
        )

        # Create REAL notifications in test database
        self.notifications = []
        for i in range(3):
            notification = Notification.objects.create(
                recipient=self.user,
                recipient_email=self.user_email,
                subject=f"Test Notification {i}",
                message=f"Test message body {i}",
                notification_type=Notification.EMAIL,
                status=Notification.SENT,
                metadata={"template_type": "recipe_published"},
            )
            self.notifications.append(notification)

    def tearDown(self):
        """Clean up after tests."""
        post_save.connect(send_welcome_email, sender=User)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_user_scope_returns_200(
        self,
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

        # Execute - uses REAL database and pagination
        response = self.client.get(self.url)

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("results", data)
        self.assertIn("count", data)
        self.assertIn("next", data)
        self.assertIn("previous", data)
        self.assertEqual(data["count"], 3)
        self.assertEqual(len(data["results"]), 3)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_admin_scope_returns_200(
        self,
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

        # Execute - uses REAL database
        response = self.client.get(self.url)

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 3)

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
    def test_get_with_status_filter_applies_filter(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
    ):
        """Test GET with status filter applies the filter correctly."""
        # Create one notification with "pending" status
        Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user_email,
            subject="Pending Notification",
            message="Pending message",
            notification_type=Notification.EMAIL,
            status=Notification.PENDING,
        )

        # Setup authentication
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)
        mock_get_current_user.return_value = user
        mock_require_current_user.return_value = user

        # Execute with status filter for "sent" - should only return the 3 from setUp
        response = self.client.get(self.url, {"status": "sent"})

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 3)  # Only the 3 "sent" notifications

        # Test filtering for "pending"
        response = self.client.get(self.url, {"status": "pending"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)  # Only the 1 "pending" notification

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
    def test_get_excludes_message_by_default(
        self,
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

        # Execute without include_message parameter
        response = self.client.get(self.url)

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(len(data["results"]), 0)
        # Message field should be excluded
        self.assertNotIn("message", data["results"][0])

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_includes_message_when_requested(
        self,
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

        # Execute with include_message=true
        response = self.client.get(self.url, {"include_message": "true"})

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(len(data["results"]), 0)
        # Message field should be included
        self.assertIn("message", data["results"][0])
        # Results are ordered by created_at DESC, so most recent (index 2) comes first
        self.assertEqual(data["results"][0]["message"], "Test message body 2")

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_pagination_params(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
    ):
        """Test GET with pagination parameters."""
        # Create a large number of notifications for pagination testing
        for i in range(30):  # Total of 33 notifications (3 from setUp + 30 here)
            Notification.objects.create(
                recipient=self.user,
                recipient_email=self.user_email,
                subject=f"Pagination Test {i}",
                message=f"Message {i}",
                notification_type=Notification.EMAIL,
                status=Notification.SENT,
            )

        # Setup authentication
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)
        mock_get_current_user.return_value = user
        mock_require_current_user.return_value = user

        # Execute with pagination params - page 2, 10 per page
        response = self.client.get(self.url, {"page": "2", "page_size": "10"})

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 33)  # Total notifications
        self.assertEqual(len(data["results"]), 10)  # Page size
        self.assertIsNotNone(data["next"])  # Should have next page
        self.assertIsNotNone(data["previous"])  # Should have previous page

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_user_not_found_returns_empty(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
    ):
        """Test GET when user not found in local DB returns empty results."""
        # Create a user ID that doesn't exist in the database
        non_existent_user_id = uuid4()

        # Setup authentication with non-existent user
        user = OAuth2User(
            user_id=str(non_existent_user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)
        mock_get_current_user.return_value = user
        mock_require_current_user.return_value = user

        # Execute
        response = self.client.get(self.url)

        # Assertions - should return empty list since user doesn't exist
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 0)
        self.assertEqual(len(data["results"]), 0)


class TestUserNotificationsByIdEndpoint(TestCase):
    """Component tests for GET /users/{userId}/notifications."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.user_id = uuid4()
        self.admin_id = uuid4()
        self.user_email = "user@example.com"

        post_save.disconnect(send_welcome_email, sender=User)

        # Create REAL user in test database
        self.user = User.objects.create(
            user_id=self.user_id,
            email=self.user_email,
            username="testuser",
            password_hash="test_hash",
        )

        # Create REAL notifications in test database
        self.notifications = []
        for i in range(3):
            notification = Notification.objects.create(
                recipient=self.user,
                recipient_email=self.user_email,
                subject=f"Test Notification {i}",
                message=f"Test message body {i}",
                notification_type=Notification.EMAIL,
                status=Notification.SENT,
                metadata={"template_type": "recipe_published"},
            )
            self.notifications.append(notification)

    def tearDown(self):
        """Clean up after tests."""
        post_save.connect(send_welcome_email, sender=User)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_admin_scope_returns_200(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
    ):
        """Test GET with admin scope returns HTTP 200 with notifications."""
        # Setup admin authentication
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        # Execute - uses REAL database and pagination
        url = f"/api/v1/notification/users/{self.user_id}/notifications"
        response = self.client.get(url)

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("results", data)
        self.assertIn("count", data)
        self.assertIn("next", data)
        self.assertIn("previous", data)
        self.assertEqual(data["count"], 3)
        self.assertEqual(len(data["results"]), 3)

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_without_admin_scope_returns_403(self, mock_authenticate):
        """Test GET without admin scope returns HTTP 403."""
        # Setup authentication with user scope (not admin)
        user = OAuth2User(
            user_id=str(self.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (user, None)

        # Execute
        url = f"/api/v1/notification/users/{self.user_id}/notifications"
        response = self.client.get(url)

        # Assertions
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertEqual(data["error"], "forbidden")
        self.assertIn("notification:admin", data["detail"])

    def test_get_without_authentication_returns_401(self):
        """Test GET without authentication returns HTTP 401."""
        # Execute without any authentication
        url = f"/api/v1/notification/users/{self.user_id}/notifications"
        response = self.client.get(url)

        # Assertions
        # DRF returns 403 when authentication is missing and permission classes are set
        # The actual status depends on the DRF configuration
        self.assertIn(response.status_code, [401, 403])

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_invalid_user_id_returns_400(self, mock_authenticate):
        """Test GET with invalid user ID format returns HTTP 400."""
        # Setup admin authentication
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)

        # Execute with invalid UUID
        url = "/api/v1/notification/users/not-a-valid-uuid/notifications"
        response = self.client.get(url)

        # Assertions
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "bad_request")
        self.assertIn("Invalid user ID format", data["message"])

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_nonexistent_user_returns_404(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
    ):
        """Test GET with non-existent user ID returns HTTP 404."""
        # Setup admin authentication
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        # Execute with non-existent user ID
        non_existent_user_id = uuid4()
        url = f"/api/v1/notification/users/{non_existent_user_id}/notifications"
        response = self.client.get(url)

        # Assertions
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["error"], "not_found")

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_status_filter_applies_filter(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
    ):
        """Test GET with status filter applies the filter correctly."""
        # Create one notification with "pending" status
        Notification.objects.create(
            recipient=self.user,
            recipient_email=self.user_email,
            subject="Pending Notification",
            message="Pending message",
            notification_type=Notification.EMAIL,
            status=Notification.PENDING,
        )

        # Setup admin authentication
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        # Execute with status filter for "sent" - should only return the 3 from setUp
        url = f"/api/v1/notification/users/{self.user_id}/notifications"
        response = self.client.get(url, {"status": "sent"})

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 3)  # Only the 3 "sent" notifications

        # Test filtering for "pending"
        response = self.client.get(url, {"status": "pending"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)  # Only the 1 "pending" notification

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_invalid_status_returns_400(self, mock_authenticate):
        """Test GET with invalid status filter returns HTTP 400."""
        # Setup admin authentication
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)

        # Execute with invalid status
        url = f"/api/v1/notification/users/{self.user_id}/notifications"
        response = self.client.get(url, {"status": "invalid_status"})

        # Assertions
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"], "bad_request")

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_excludes_message_by_default(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
    ):
        """Test GET excludes message field by default."""
        # Setup admin authentication
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        # Execute without include_message parameter
        url = f"/api/v1/notification/users/{self.user_id}/notifications"
        response = self.client.get(url)

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(len(data["results"]), 0)
        # Message field should be excluded
        self.assertNotIn("message", data["results"][0])

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_includes_message_when_requested(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
    ):
        """Test GET includes message field when include_message=true."""
        # Setup admin authentication
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        # Execute with include_message=true
        url = f"/api/v1/notification/users/{self.user_id}/notifications"
        response = self.client.get(url, {"include_message": "true"})

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(len(data["results"]), 0)
        # Message field should be included
        self.assertIn("message", data["results"][0])
        # Results are ordered by created_at DESC, so most recent (index 2) comes first
        self.assertEqual(data["results"][0]["message"], "Test message body 2")

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_get_with_pagination_params(
        self,
        mock_authenticate,
        mock_require_current_user,
        mock_get_current_user,
    ):
        """Test GET with pagination parameters."""
        # Create a large number of notifications for pagination testing
        for i in range(30):  # Total of 33 notifications (3 from setUp + 30 here)
            Notification.objects.create(
                recipient=self.user,
                recipient_email=self.user_email,
                subject=f"Pagination Test {i}",
                message=f"Message {i}",
                notification_type=Notification.EMAIL,
                status=Notification.SENT,
            )

        # Setup admin authentication
        admin_user = OAuth2User(
            user_id=str(self.admin_id),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user
        mock_require_current_user.return_value = admin_user

        # Execute with pagination params - page 2, 10 per page
        url = f"/api/v1/notification/users/{self.user_id}/notifications"
        response = self.client.get(url, {"page": "2", "page_size": "10"})

        # Assertions
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 33)  # Total notifications
        self.assertEqual(len(data["results"]), 10)  # Page size
        self.assertIsNotNone(data["next"])  # Should have next page
        self.assertIsNotNone(data["previous"])  # Should have previous page
