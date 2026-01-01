"""Component tests for recipe-trending notification endpoint.

This module tests the /notifications/recipe-trending endpoint through the
full Django request/response cycle, including authentication, authorization,
and HTTP handling.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import Client, TestCase

from core.auth.oauth2 import OAuth2User
from core.exceptions import RecipeNotFoundError
from core.schemas.recipe import RecipeDto
from core.schemas.user import UserSearchResult


class TestRecipeTrendingEndpoint(TestCase):
    """Component tests for recipe trending notification endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.url = "/api/v1/notification/notifications/recipe-trending"

        # Test data
        self.recipe_id = 123
        self.recipient_ids = [uuid4(), uuid4()]

        self.request_data = {
            "recipe_id": self.recipe_id,
            "recipient_ids": [str(rid) for rid in self.recipient_ids],
            "trending_metrics": "1,234 views and 89 likes in the past 24 hours",
        }

        # Mock recipe
        self.mock_recipe = RecipeDto(
            recipe_id=self.recipe_id,
            user_id=uuid4(),
            title="Test Recipe",
            servings=Decimal("4"),
            created_at="2025-10-29T12:00:00Z",
        )

        # Mock user
        self.mock_user = UserSearchResult(
            user_id=uuid4(),
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    @patch("core.services.recipe_notification_service.User.objects")
    def test_post_with_admin_scope_returns_202(
        self,
        mock_user_objects,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
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
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user

        mock_db_user = Mock()
        mock_db_user.user_id = uuid4()
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
        # Setup authentication with user scope (not admin)
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

        # Invalid payload - missing recipe_id
        invalid_data = {
            "recipient_ids": [str(uuid4())],
            # Missing recipe_id
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
            "recipe_id": self.recipe_id,
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
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    def test_post_with_nonexistent_recipe_returns_404(
        self, mock_recipe_client, mock_authenticate, mock_get_current_user
    ):
        """Test POST with nonexistent recipe returns HTTP 404."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup recipe client to raise RecipeNotFoundError
        mock_recipe_client.get_recipe.side_effect = RecipeNotFoundError(
            recipe_id=int(self.recipe_id)
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
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    @patch("core.services.recipe_notification_service.User.objects")
    def test_response_contains_notification_ids(
        self,
        mock_user_objects,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test response contains notification IDs and count."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup service mocks
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user

        mock_db_user = Mock()
        mock_db_user.user_id = uuid4()
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
        self.assertIn("notifications", data)
        self.assertIn("queued_count", data)
        self.assertIn("message", data)
        self.assertEqual(len(data["notifications"]), 2)
        for notification in data["notifications"]:
            self.assertIn("notification_id", notification)
            self.assertIn("recipient_id", notification)

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    @patch("core.services.recipe_notification_service.User.objects")
    def test_post_without_trending_metrics_succeeds(
        self,
        mock_user_objects,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test POST without trending_metrics (optional field) succeeds."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup service mocks
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user

        mock_db_user = Mock()
        mock_db_user.user_id = uuid4()
        mock_user_objects.get.return_value = mock_db_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = (
            mock_notification,
            [],
        )

        # Request without trending_metrics
        request_data = {
            "recipe_id": self.recipe_id,
            "recipient_ids": [str(rid) for rid in self.recipient_ids],
        }

        # Execute
        response = self.client.post(
            self.url,
            data=request_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 202)
