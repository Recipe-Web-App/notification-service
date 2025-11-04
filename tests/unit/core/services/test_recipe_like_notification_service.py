"""Tests for RecipeNotificationService recipe-liked functionality."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import TestCase

from rest_framework.exceptions import PermissionDenied

from core.auth.oauth2 import OAuth2User
from core.exceptions import RecipeNotFoundError
from core.schemas.notification import RecipeLikedRequest
from core.schemas.recipe import RecipeDto
from core.schemas.user import UserSearchResult
from core.services.recipe_notification_service import (
    RecipeNotificationService,
)


class TestRecipeLikedNotifications(TestCase):
    """Test suite for recipe-liked notifications."""

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

        self.recipe_liked_request = RecipeLikedRequest(
            recipient_ids=[uuid4(), uuid4()],
            recipe_id=uuid4(),
            liker_id=uuid4(),
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
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = self.service.send_recipe_liked_notifications(
            request=self.recipe_liked_request,
        )

        # Assertions
        self.assertEqual(response.queued_count, 2)
        self.assertEqual(len(response.notifications), 2)
        self.assertEqual(response.message, "Notifications queued successfully")

        # Verify recipe was fetched
        mock_recipe_client.get_recipe.assert_called_once_with(
            int(self.recipe_liked_request.recipe_id)
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
        """Test sending notifications with user scope validates liker follows author."""
        mock_require_current_user.return_value = self.regular_user
        # Setup mocks
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user
        # Liker is a valid follower of the author
        mock_user_client.validate_follower_relationship.return_value = True

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = self.service.send_recipe_liked_notifications(
            request=self.recipe_liked_request,
        )

        # Assertions
        self.assertEqual(response.queued_count, 2)
        self.assertEqual(len(response.notifications), 2)

        # Verify follower validation was called once (for liker)
        self.assertEqual(mock_user_client.validate_follower_relationship.call_count, 1)

    @patch("core.services.recipe_notification_service.require_current_user")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    def test_send_notifications_recipe_not_found(
        self,
        mock_recipe_client,
        mock_require_current_user,
    ):
        """Test recipe not found raises RecipeNotFoundError."""
        mock_require_current_user.return_value = self.regular_user
        # Setup mock to raise RecipeNotFoundError
        mock_recipe_client.get_recipe.side_effect = RecipeNotFoundError(
            recipe_id=int(self.recipe_liked_request.recipe_id)
        )

        # Execute and assert
        with self.assertRaises(RecipeNotFoundError):
            self.service.send_recipe_liked_notifications(
                request=self.recipe_liked_request,
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
        """Test liker not following author raises PermissionDenied."""
        mock_require_current_user.return_value = self.regular_user
        # Setup mocks
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        # Liker is not a follower of the author
        mock_user_client.validate_follower_relationship.return_value = False

        # Execute and assert
        with self.assertRaises(PermissionDenied) as exc_info:
            self.service.send_recipe_liked_notifications(
                request=self.recipe_liked_request,
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
        """Test email template is rendered with correct context."""
        mock_require_current_user.return_value = self.admin_user
        # Setup mocks
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user
        mock_render.return_value = "<html>Test email</html>"

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        self.service.send_recipe_liked_notifications(
            request=self.recipe_liked_request,
        )

        # Verify template was rendered
        self.assertEqual(mock_render.call_count, 2)
        first_call = mock_render.call_args_list[0]
        self.assertEqual(first_call[0][0], "emails/recipe_liked.html")
        self.assertIn("recipient_name", first_call[0][1])
        self.assertIn("liker_name", first_call[0][1])
        self.assertIn("recipe_title", first_call[0][1])
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
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        self.service.send_recipe_liked_notifications(
            request=self.recipe_liked_request,
        )

        # Verify metadata was included in notification creation
        call_args = mock_notification_service.create_notification.call_args
        metadata = call_args[1]["metadata"]

        self.assertEqual(metadata["template_type"], "recipe_liked")
        self.assertEqual(
            metadata["recipe_id"], str(self.recipe_liked_request.recipe_id)
        )
        self.assertEqual(metadata["liker_id"], str(self.recipe_liked_request.liker_id))

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
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        self.service.send_recipe_liked_notifications(
            request=self.recipe_liked_request,
        )

        # Verify queue flag was set to True
        call_args = mock_notification_service.create_notification.call_args
        self.assertIs(call_args[1]["auto_queue"], True)

    @patch("core.services.recipe_notification_service.require_current_user")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    def test_send_notifications_multiple_recipients(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_require_current_user,
    ):
        """Test handling multiple recipients correctly."""
        mock_require_current_user.return_value = self.admin_user
        # Create request with 3 recipients
        request = RecipeLikedRequest(
            recipient_ids=[uuid4(), uuid4(), uuid4()],
            recipe_id=uuid4(),
            liker_id=uuid4(),
        )

        # Setup mocks
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = self.service.send_recipe_liked_notifications(
            request=request,
        )

        # Assertions
        self.assertEqual(response.queued_count, 3)
        self.assertEqual(len(response.notifications), 3)
        self.assertEqual(mock_notification_service.create_notification.call_count, 3)
