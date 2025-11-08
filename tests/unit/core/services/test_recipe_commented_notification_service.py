"""Tests for RecipeNotificationService recipe-commented functionality."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import TestCase

from rest_framework.exceptions import PermissionDenied

from core.auth.oauth2 import OAuth2User
from core.exceptions import CommentNotFoundError, RecipeNotFoundError
from core.schemas.notification import RecipeCommentedRequest
from core.schemas.recipe import CommentDto, RecipeDto
from core.schemas.user import UserSearchResult
from core.services.recipe_notification_service import (
    RecipeNotificationService,
)


class TestRecipeCommentedNotifications(TestCase):
    """Test suite for recipe-commented notifications."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = RecipeNotificationService()

        self.admin_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )

        self.regular_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:user"],
        )

        self.recipe_commented_request = RecipeCommentedRequest(
            recipient_ids=[uuid4(), uuid4()],
            comment_id=456,
        )

        self.mock_comment = CommentDto(
            comment_id=456,
            recipe_id=123,
            user_id=uuid4(),
            comment_text="This recipe looks delicious! I can't wait to try it.",
            created_at=datetime.now(UTC),
        )

        self.mock_recipe = RecipeDto(
            recipe_id=123,
            user_id=uuid4(),
            title="Test Recipe",
            servings=Decimal("4"),
            created_at="2025-10-29T12:00:00Z",
        )

        self.mock_user = UserSearchResult(
            user_id=uuid4(),
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @patch("core.services.recipe_notification_service.require_current_user")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    def test_send_notifications_admin_scope_success(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_require_current_user,
    ):
        """Test sending notifications with admin scope bypasses follower check."""
        mock_require_current_user.return_value = self.admin_user
        # Setup mocks
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = self.service.send_recipe_commented_notifications(
            request=self.recipe_commented_request,
        )

        # Assertions
        self.assertEqual(response.queued_count, 2)
        self.assertEqual(len(response.notifications), 2)
        self.assertEqual(response.message, "Notifications queued successfully")

        # Verify comment was fetched
        mock_recipe_client.get_comment.assert_called_once_with(
            self.recipe_commented_request.comment_id
        )

        # Verify recipe was fetched
        mock_recipe_client.get_recipe.assert_called_once_with(
            self.mock_comment.recipe_id
        )

        # Verify follower validation was NOT called (admin bypass)
        mock_user_client.validate_follower_relationship.assert_not_called()

        # Verify notification service called for each recipient
        self.assertEqual(mock_notification_service.create_notification.call_count, 2)

    @patch("core.services.recipe_notification_service.require_current_user")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    def test_send_notifications_user_scope_with_valid_follower(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_require_current_user,
    ):
        """Test user scope validates commenter follows author."""
        mock_require_current_user.return_value = self.regular_user
        # Setup mocks
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user
        # Commenter is a valid follower of the author
        mock_user_client.validate_follower_relationship.return_value = True

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = self.service.send_recipe_commented_notifications(
            request=self.recipe_commented_request,
        )

        # Assertions
        self.assertEqual(response.queued_count, 2)
        self.assertEqual(len(response.notifications), 2)

        # Verify follower validation was called once (for commenter)
        self.assertEqual(mock_user_client.validate_follower_relationship.call_count, 1)

    @patch("core.services.recipe_notification_service.require_current_user")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    def test_send_notifications_comment_not_found(
        self,
        mock_recipe_client,
        mock_require_current_user,
    ):
        """Test comment not found raises CommentNotFoundError."""
        mock_require_current_user.return_value = self.admin_user
        # Setup mock to raise CommentNotFoundError
        mock_recipe_client.get_comment.side_effect = CommentNotFoundError(
            comment_id=str(self.recipe_commented_request.comment_id)
        )

        # Execute and assert
        with self.assertRaises(CommentNotFoundError):
            self.service.send_recipe_commented_notifications(
                request=self.recipe_commented_request,
            )

    @patch("core.services.recipe_notification_service.require_current_user")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    def test_send_notifications_recipe_not_found(
        self,
        mock_recipe_client,
        mock_require_current_user,
    ):
        """Test recipe not found raises RecipeNotFoundError."""
        mock_require_current_user.return_value = self.regular_user
        # Setup mocks
        mock_recipe_client.get_comment.return_value = self.mock_comment
        # Recipe not found after fetching comment
        mock_recipe_client.get_recipe.side_effect = RecipeNotFoundError(
            recipe_id=self.mock_comment.recipe_id
        )

        # Execute and assert
        with self.assertRaises(RecipeNotFoundError):
            self.service.send_recipe_commented_notifications(
                request=self.recipe_commented_request,
            )

    @patch("core.services.recipe_notification_service.require_current_user")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    def test_send_notifications_invalid_follower_relationship(
        self,
        mock_user_client,
        mock_recipe_client,
        mock_require_current_user,
    ):
        """Test commenter not following author raises PermissionDenied."""
        mock_require_current_user.return_value = self.regular_user
        # Setup mocks
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        # Commenter is not a follower of the author
        mock_user_client.validate_follower_relationship.return_value = False

        # Execute and assert
        with self.assertRaises(PermissionDenied) as exc_info:
            self.service.send_recipe_commented_notifications(
                request=self.recipe_commented_request,
            )

        self.assertIn("not a follower", str(exc_info.exception.detail).lower())

    @patch("core.services.recipe_notification_service.require_current_user")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    @patch("core.services.recipe_notification_service.render_to_string")
    def test_send_notifications_renders_email_template(
        self,
        mock_render,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_require_current_user,
    ):
        """Test email template rendered with context including comment preview."""
        mock_require_current_user.return_value = self.admin_user
        # Setup mocks
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user
        mock_render.return_value = "<html>Test email</html>"

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        self.service.send_recipe_commented_notifications(
            request=self.recipe_commented_request,
        )

        # Verify template was rendered
        self.assertEqual(mock_render.call_count, 2)
        first_call = mock_render.call_args_list[0]
        self.assertEqual(first_call[0][0], "emails/recipe_commented.html")
        self.assertIn("recipient_name", first_call[0][1])
        self.assertIn("commenter_name", first_call[0][1])
        self.assertIn("recipe_title", first_call[0][1])
        self.assertIn("comment_preview", first_call[0][1])
        self.assertIn("recipe_url", first_call[0][1])

    @patch("core.services.recipe_notification_service.require_current_user")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    def test_send_notifications_includes_metadata(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_require_current_user,
    ):
        """Test notifications include correct metadata."""
        mock_require_current_user.return_value = self.admin_user
        # Setup mocks
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        self.service.send_recipe_commented_notifications(
            request=self.recipe_commented_request,
        )

        # Verify metadata was included in notification creation
        call_args = mock_notification_service.create_notification.call_args
        metadata = call_args[1]["metadata"]

        self.assertEqual(metadata["template_type"], "recipe_commented")
        self.assertEqual(
            metadata["comment_id"], str(self.recipe_commented_request.comment_id)
        )
        self.assertEqual(metadata["recipe_id"], str(self.mock_comment.recipe_id))
        self.assertEqual(metadata["commenter_id"], str(self.mock_comment.user_id))

    @patch("core.services.recipe_notification_service.require_current_user")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    def test_send_notifications_queue_flag_enabled(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_require_current_user,
    ):
        """Test notifications are queued for async processing."""
        mock_require_current_user.return_value = self.admin_user
        # Setup mocks
        mock_recipe_client.get_comment.return_value = self.mock_comment
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        self.service.send_recipe_commented_notifications(
            request=self.recipe_commented_request,
        )

        # Verify queue flag was set to True
        call_args = mock_notification_service.create_notification.call_args
        self.assertIs(call_args[1]["auto_queue"], True)
