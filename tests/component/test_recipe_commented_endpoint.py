"""Component tests for recipe-commented notification endpoint.

This module tests the /notifications/recipe-commented endpoint through the
full Django request/response cycle, including authentication, authorization,
and HTTP handling.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import Client, TestCase

from core.auth.oauth2 import OAuth2User
from core.exceptions import CommentNotFoundError, RecipeNotFoundError, UserNotFoundError
from core.schemas.recipe import CommentDto, RecipeDto
from core.schemas.user import UserSearchResult


class TestRecipeCommentedEndpoint(TestCase):
    """Component tests for recipe commented notification endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.url = "/api/v1/notification/notifications/recipe-commented"

        # Test data
        self.comment_id = uuid4()
        self.recipient_ids = [uuid4(), uuid4()]

        self.request_data = {
            "comment_id": str(self.comment_id),
            "recipient_ids": [str(rid) for rid in self.recipient_ids],
        }

        # Mock comment
        self.mock_comment = CommentDto(
            comment_id=self.comment_id,
            recipe_id=123,
            user_id=uuid4(),
            comment_text="This recipe looks delicious!",
            created_at=datetime.now(UTC),
        )

        # Mock recipe
        self.mock_recipe = RecipeDto(
            recipe_id=123,
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

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    def test_post_with_admin_scope_returns_202(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_authenticate,
    ):
        """Test POST with admin scope returns HTTP 202."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)

        # Setup service mocks
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user

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
        self.assertEqual(data["queued_count"], 2)
        self.assertEqual(len(data["notifications"]), 2)
        self.assertEqual(data["message"], "Notifications queued successfully")

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    def test_post_with_user_scope_and_valid_follower_returns_202(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_authenticate,
    ):
        """Test POST with user scope and valid follower returns HTTP 202."""
        # Setup authentication
        regular_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (regular_user, None)

        # Setup service mocks
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user
        mock_user_client.validate_follower_relationship.return_value = True

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

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_without_authentication_returns_401(self, mock_authenticate):
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

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_without_required_scope_returns_403(self, mock_authenticate):
        """Test POST without required scope returns HTTP 403."""
        # Setup authentication with wrong scope
        user_without_scope = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["some:other:scope"],
        )
        mock_authenticate.return_value = (user_without_scope, None)

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertIn("notification:user", data["detail"])

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    def test_post_with_invalid_follower_returns_403(
        self,
        mock_user_client,
        mock_recipe_client,
        mock_authenticate,
    ):
        """Test POST with commenter not following author returns HTTP 403."""
        # Setup authentication
        regular_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_authenticate.return_value = (regular_user, None)

        # Setup service mocks
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        # Commenter doesn't follow author
        mock_user_client.validate_follower_relationship.return_value = False

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 403)

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_invalid_payload_returns_400(self, mock_authenticate):
        """Test POST with invalid payload returns HTTP 400."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)

        # Invalid payload - missing comment_id
        invalid_data = {
            "recipient_ids": [str(uuid4())],
            # Missing comment_id
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

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_empty_recipient_list_returns_400(self, mock_authenticate):
        """Test POST with empty recipient list returns HTTP 400."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)

        # Invalid payload - empty recipient_ids
        invalid_data = {
            "comment_id": str(uuid4()),
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

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_too_many_recipients_returns_400(self, mock_authenticate):
        """Test POST with >100 recipients returns HTTP 400."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)

        # Invalid payload - too many recipients
        invalid_data = {
            "comment_id": str(uuid4()),
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

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    def test_post_with_nonexistent_comment_returns_404(
        self,
        mock_recipe_client,
        mock_authenticate,
    ):
        """Test POST with nonexistent comment returns HTTP 404."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)

        # Setup recipe client to raise CommentNotFoundError
        mock_recipe_client.get_comment.side_effect = CommentNotFoundError(
            comment_id=str(self.comment_id)
        )

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 404)

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    def test_post_with_nonexistent_recipe_returns_404(
        self,
        mock_recipe_client,
        mock_authenticate,
    ):
        """Test POST with nonexistent recipe returns HTTP 404."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)

        # Setup recipe client
        mock_recipe_client.get_comment.return_value = self.mock_comment
        # Recipe not found after getting comment
        mock_recipe_client.get_recipe.side_effect = RecipeNotFoundError(
            recipe_id=self.mock_comment.recipe_id
        )

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 404)

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    def test_post_with_nonexistent_commenter_returns_404(
        self,
        mock_user_client,
        mock_recipe_client,
        mock_authenticate,
    ):
        """Test POST with nonexistent commenter returns HTTP 404."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)

        # Setup service mocks
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        # User client raises UserNotFoundError when fetching commenter
        mock_user_client.get_user.side_effect = UserNotFoundError(
            user_id=str(self.mock_comment.user_id)
        )

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 404)

    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    def test_response_contains_notification_ids(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_authenticate,
    ):
        """Test response contains notification IDs for each recipient."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)

        # Setup service mocks
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user

        # Return different notification IDs for each call
        notification_ids = [uuid4(), uuid4()]
        notifications = [Mock(notification_id=nid) for nid in notification_ids]
        mock_notification_service.create_notification.side_effect = notifications

        # Execute
        response = self.client.post(
            self.url,
            data=self.request_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 202)

        data = response.json()
        self.assertEqual(len(data["notifications"]), 2)

        # Verify each notification has an ID and recipient_id
        for i, notification in enumerate(data["notifications"]):
            self.assertIn("notification_id", notification)
            self.assertIn("recipient_id", notification)
            self.assertEqual(notification["notification_id"], str(notification_ids[i]))
            self.assertEqual(notification["recipient_id"], str(self.recipient_ids[i]))
