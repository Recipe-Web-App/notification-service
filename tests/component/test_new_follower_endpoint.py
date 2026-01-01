"""Component tests for new-follower notification endpoint.

This module tests the /notifications/new-follower endpoint through the
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


class TestNewFollowerEndpoint(TestCase):
    """Component tests for new follower notification endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.url = "/api/v1/notification/notifications/new-follower"

        # Test data
        self.follower_id = uuid4()
        self.recipient_ids = [uuid4()]

        self.request_data = {
            "follower_id": str(self.follower_id),
            "recipient_ids": [str(rid) for rid in self.recipient_ids],
        }

        # Mock follower user
        self.mock_follower = UserSearchResult(
            user_id=self.follower_id,
            username="newfollower",
            email="follower@example.com",
            full_name="New Follower",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock recipient user
        self.mock_recipient = UserSearchResult(
            user_id=self.recipient_ids[0],
            username="recipient",
            email="recipient@example.com",
            full_name="Recipient User",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.social_notification_service.user_client")
    @patch("core.services.social_notification_service.recipe_management_service_client")
    @patch("core.services.social_notification_service.notification_service")
    @patch("core.services.social_notification_service.User.objects")
    def test_post_with_admin_scope_returns_202(
        self,
        mock_user_objects,
        mock_notification_service,
        mock_recipe_client,
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
        mock_user_client.get_user.side_effect = [
            self.mock_follower,
            self.mock_recipient,
        ]
        mock_user_client.validate_follower_relationship.return_value = True
        mock_recipe_client.get_user_recipe_count.return_value = 5

        mock_db_user = Mock()
        mock_db_user.user_id = self.recipient_ids[0]
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
    @patch("core.services.social_notification_service.user_client")
    def test_post_with_nonexistent_relationship_returns_403(
        self, mock_user_client, mock_authenticate, mock_get_current_user
    ):
        """Test POST when follower relationship doesn't exist returns HTTP 403."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup service mocks - follower exists but relationship doesn't
        mock_user_client.get_user.return_value = self.mock_follower
        mock_user_client.validate_follower_relationship.return_value = False

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertIn("does not exist", data["detail"])

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
            "follower_id": str(uuid4()),
            # Missing recipient_ids
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
            "follower_id": str(uuid4()),
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
    def test_post_with_too_many_recipients_returns_400(
        self, mock_authenticate, mock_get_current_user
    ):
        """Test POST with >100 recipients returns HTTP 400."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Invalid payload - too many recipients
        invalid_data = {
            "follower_id": str(uuid4()),
            "recipient_ids": [str(uuid4()) for _ in range(101)],
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
    @patch("core.services.social_notification_service.user_client")
    def test_post_with_nonexistent_follower_returns_404(
        self, mock_user_client, mock_authenticate, mock_get_current_user
    ):
        """Test POST with nonexistent follower returns HTTP 404."""
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
            user_id=str(self.follower_id)
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
    @patch("core.services.social_notification_service.user_client")
    @patch("core.services.social_notification_service.recipe_management_service_client")
    def test_post_with_nonexistent_recipient_returns_404(
        self,
        mock_recipe_client,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test POST with nonexistent recipient returns HTTP 404."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup service mocks - follower exists, relationship valid,
        # but recipient doesn't exist
        mock_user_client.get_user.side_effect = [
            self.mock_follower,  # First call for follower
            UserNotFoundError(user_id=str(self.recipient_ids[0])),  # Second call fails
        ]
        mock_user_client.validate_follower_relationship.return_value = True
        mock_recipe_client.get_user_recipe_count.return_value = 5

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
    @patch("core.services.social_notification_service.user_client")
    @patch("core.services.social_notification_service.recipe_management_service_client")
    @patch("core.services.social_notification_service.notification_service")
    @patch("core.services.social_notification_service.User.objects")
    def test_response_contains_notification_ids(
        self,
        mock_user_objects,
        mock_notification_service,
        mock_recipe_client,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test response contains notification IDs for each recipient."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup service mocks
        mock_user_client.get_user.side_effect = [
            self.mock_follower,
            self.mock_recipient,
        ]
        mock_user_client.validate_follower_relationship.return_value = True
        mock_recipe_client.get_user_recipe_count.return_value = 3

        mock_db_user = Mock()
        mock_db_user.user_id = self.recipient_ids[0]
        mock_user_objects.get.return_value = mock_db_user

        # Create mock notification with ID
        notification_id = uuid4()
        mock_notification = Mock(notification_id=notification_id)
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
        self.assertEqual(len(data["notifications"]), 1)

        # Verify notification has ID and recipient_id
        notification = data["notifications"][0]
        self.assertIn("notification_id", notification)
        self.assertIn("recipient_id", notification)
        self.assertEqual(notification["notification_id"], str(notification_id))
        self.assertEqual(notification["recipient_id"], str(self.recipient_ids[0]))

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.social_notification_service.user_client")
    @patch("core.services.social_notification_service.recipe_management_service_client")
    @patch("core.services.social_notification_service.notification_service")
    @patch("core.services.social_notification_service.User.objects")
    def test_recipe_count_is_fetched(
        self,
        mock_user_objects,
        mock_notification_service,
        mock_recipe_client,
        mock_user_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test that recipe count is fetched from recipe service."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup service mocks
        mock_user_client.get_user.side_effect = [
            self.mock_follower,
            self.mock_recipient,
        ]
        mock_user_client.validate_follower_relationship.return_value = True
        mock_recipe_client.get_user_recipe_count.return_value = 10

        mock_db_user = Mock()
        mock_db_user.user_id = self.recipient_ids[0]
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
            data=self.request_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 202)

        # Verify recipe count was fetched
        mock_recipe_client.get_user_recipe_count.assert_called_once_with(
            str(self.follower_id)
        )
