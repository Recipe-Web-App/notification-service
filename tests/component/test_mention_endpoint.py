"""Component tests for mention notification endpoint.

This module tests the /notifications/mention endpoint through the
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


class TestMentionEndpoint(TestCase):
    """Component tests for mention notification endpoint."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.url = "/api/v1/notification/notifications/mention"

        # Test data
        self.comment_id = 456
        self.commenter_id = uuid4()
        self.recipe_id = 123
        self.recipient_ids = [uuid4()]

        self.request_data = {
            "comment_id": self.comment_id,
            "recipient_ids": [str(rid) for rid in self.recipient_ids],
        }

        # Mock comment
        self.mock_comment = CommentDto(
            comment_id=self.comment_id,
            recipe_id=self.recipe_id,
            user_id=self.commenter_id,
            comment_text="This is a great recipe! Thanks @user for sharing!",
            created_at=datetime.now(UTC),
        )

        # Mock commenter user
        self.mock_commenter = UserSearchResult(
            user_id=self.commenter_id,
            username="commenter",
            email="commenter@example.com",
            full_name="Commenter User",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Mock recipe
        self.mock_recipe = RecipeDto(
            recipe_id=self.recipe_id,
            user_id=uuid4(),
            title="Amazing Chocolate Cake",
            servings=Decimal("8"),
            created_at=datetime.now(UTC),
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
    @patch("core.services.social_notification_service.recipe_management_service_client")
    @patch("core.services.social_notification_service.user_client")
    @patch("core.services.social_notification_service.notification_service")
    def test_post_with_admin_scope_returns_202(
        self,
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
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_user_client.get_user.side_effect = [
            self.mock_commenter,
            self.mock_recipient,
        ]
        mock_recipe_client.get_recipe.return_value = self.mock_recipe

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
            "comment_id": str(uuid4()),
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

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    def test_post_with_invalid_uuid_returns_400(
        self, mock_authenticate, mock_get_current_user
    ):
        """Test POST with invalid UUID format returns HTTP 400."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Invalid payload - invalid UUID
        invalid_data = {
            "comment_id": "not-a-uuid",
            "recipient_ids": [str(uuid4())],
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
    @patch("core.services.social_notification_service.recipe_management_service_client")
    def test_post_with_nonexistent_comment_returns_404(
        self, mock_recipe_client, mock_authenticate, mock_get_current_user
    ):
        """Test POST with nonexistent comment returns HTTP 404."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

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

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.social_notification_service.recipe_management_service_client")
    @patch("core.services.social_notification_service.user_client")
    def test_post_with_nonexistent_commenter_returns_404(
        self,
        mock_user_client,
        mock_recipe_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test POST with nonexistent commenter returns HTTP 404."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup service mocks - comment exists but commenter doesn't
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_user_client.get_user.side_effect = UserNotFoundError(
            user_id=str(self.commenter_id)
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
    @patch("core.services.social_notification_service.recipe_management_service_client")
    @patch("core.services.social_notification_service.user_client")
    def test_post_with_nonexistent_recipe_returns_404(
        self,
        mock_user_client,
        mock_recipe_client,
        mock_authenticate,
        mock_get_current_user,
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

        # Setup service mocks - comment and commenter exist but recipe doesn't
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_user_client.get_user.return_value = self.mock_commenter
        mock_recipe_client.get_recipe.side_effect = RecipeNotFoundError(
            recipe_id=self.recipe_id
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
    @patch("core.services.social_notification_service.recipe_management_service_client")
    @patch("core.services.social_notification_service.user_client")
    def test_post_with_nonexistent_recipient_returns_404(
        self,
        mock_user_client,
        mock_recipe_client,
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

        # Setup service mocks - comment, commenter, recipe exist
        # but recipient doesn't exist
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_user_client.get_user.side_effect = [
            self.mock_commenter,  # First call for commenter
            UserNotFoundError(user_id=str(self.recipient_ids[0])),  # Second call fails
        ]
        mock_recipe_client.get_recipe.return_value = self.mock_recipe

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
    @patch("core.services.social_notification_service.recipe_management_service_client")
    @patch("core.services.social_notification_service.user_client")
    @patch("core.services.social_notification_service.notification_service")
    def test_response_contains_notification_ids(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
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
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_user_client.get_user.side_effect = [
            self.mock_commenter,
            self.mock_recipient,
        ]
        mock_recipe_client.get_recipe.return_value = self.mock_recipe

        # Create mock notification with ID
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
        self.assertEqual(notification["recipient_id"], str(self.recipient_ids[0]))

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.social_notification_service.recipe_management_service_client")
    @patch("core.services.social_notification_service.user_client")
    @patch("core.services.social_notification_service.notification_service")
    def test_metadata_includes_all_fields(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test notification metadata includes all required fields."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Setup service mocks
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_user_client.get_user.side_effect = [
            self.mock_commenter,
            self.mock_recipient,
        ]
        mock_recipe_client.get_recipe.return_value = self.mock_recipe

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        self.client.post(
            self.url,
            data=self.request_data,
            content_type="application/json",
        )

        # Assertions - check metadata passed to create_notification
        call_kwargs = mock_notification_service.create_notification.call_args.kwargs
        metadata = call_kwargs["metadata"]

        self.assertEqual(metadata["template_type"], "mention")
        self.assertEqual(metadata["comment_id"], str(self.comment_id))
        self.assertEqual(metadata["recipient_id"], str(self.recipient_ids[0]))
        self.assertEqual(metadata["commenter_id"], str(self.commenter_id))
        self.assertEqual(metadata["recipe_id"], str(self.recipe_id))

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.oauth2.OAuth2Authentication.authenticate")
    @patch("core.services.social_notification_service.recipe_management_service_client")
    @patch("core.services.social_notification_service.user_client")
    @patch("core.services.social_notification_service.notification_service")
    def test_multiple_recipients_handled_correctly(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_authenticate,
        mock_get_current_user,
    ):
        """Test multiple recipients are handled correctly."""
        # Setup authentication
        admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )
        mock_authenticate.return_value = (admin_user, None)
        mock_get_current_user.return_value = admin_user

        # Add second recipient
        second_recipient_id = uuid4()
        second_recipient = UserSearchResult(
            user_id=second_recipient_id,
            username="recipient2",
            email="recipient2@example.com",
            full_name="Recipient Two",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        request_data = {
            "comment_id": str(self.comment_id),
            "recipient_ids": [str(self.recipient_ids[0]), str(second_recipient_id)],
        }

        # Setup service mocks
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_user_client.get_user.side_effect = [
            self.mock_commenter,
            self.mock_recipient,
            second_recipient,
        ]
        mock_recipe_client.get_recipe.return_value = self.mock_recipe

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = self.client.post(
            self.url,
            data=request_data,
            content_type="application/json",
        )

        # Assertions
        self.assertEqual(response.status_code, 202)

        data = response.json()
        self.assertEqual(data["queued_count"], 2)
        self.assertEqual(len(data["notifications"]), 2)

        # Verify create_notification was called twice
        self.assertEqual(mock_notification_service.create_notification.call_count, 2)
