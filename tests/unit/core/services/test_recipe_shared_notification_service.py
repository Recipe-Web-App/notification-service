"""Tests for RecipeNotificationService recipe-shared functionality."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import TestCase

from core.auth.oauth2 import OAuth2User
from core.exceptions import RecipeNotFoundError, UserNotFoundError
from core.schemas.notification import RecipeSharedRequest
from core.schemas.recipe import RecipeDto
from core.schemas.user import UserSearchResult
from core.services.recipe_notification_service import (
    RecipeNotificationService,
)


class TestRecipeSharedNotifications(TestCase):
    """Test suite for recipe-shared notifications."""

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

        self.recipe_shared_request = RecipeSharedRequest(
            recipient_ids=[uuid4(), uuid4()],
            recipe_id=123,
            sharer_id=uuid4(),
            share_message="Check out this amazing recipe!",
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
    def test_send_notifications_admin_scope_reveals_sharer(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_require_current_user,
    ):
        """Test admin scope always reveals sharer identity."""
        mock_require_current_user.return_value = self.admin_user
        # Setup mocks
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = self.service.send_recipe_shared_notifications(
            request=self.recipe_shared_request,
        )

        # Assertions
        self.assertEqual(response.queued_count, 2)
        self.assertEqual(len(response.notifications), 2)
        self.assertEqual(response.message, "Notifications queued successfully")

        # Verify recipe was fetched
        mock_recipe_client.get_recipe.assert_called_once_with(
            int(self.recipe_shared_request.recipe_id)
        )

        # Verify follower validation was NOT called (admin bypass)
        mock_user_client.validate_follower_relationship.assert_not_called()

        # Verify sharer details were fetched (identity revealed)
        sharer_fetch_calls = [
            call
            for call in mock_user_client.get_user.call_args_list
            if call[0][0] == str(self.recipe_shared_request.sharer_id)
        ]
        self.assertEqual(len(sharer_fetch_calls), 1)

        # Verify notification service called for each recipient
        self.assertEqual(mock_notification_service.create_notification.call_count, 2)

    @patch("core.services.recipe_notification_service.require_current_user")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    def test_send_notifications_user_scope_follower_reveals_sharer(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_require_current_user,
    ):
        """Test user scope with follower reveals sharer identity."""
        mock_require_current_user.return_value = self.regular_user
        # Setup mocks
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user
        # Sharer follows author - identity should be revealed
        mock_user_client.validate_follower_relationship.return_value = True

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = self.service.send_recipe_shared_notifications(
            request=self.recipe_shared_request,
        )

        # Assertions
        self.assertEqual(response.queued_count, 2)
        self.assertEqual(len(response.notifications), 2)

        # Verify follower validation was called
        self.assertEqual(mock_user_client.validate_follower_relationship.call_count, 1)

        # Verify sharer details were fetched (identity revealed)
        sharer_fetch_calls = [
            call
            for call in mock_user_client.get_user.call_args_list
            if call[0][0] == str(self.recipe_shared_request.sharer_id)
        ]
        self.assertEqual(len(sharer_fetch_calls), 1)

    @patch("core.services.recipe_notification_service.require_current_user")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    def test_send_notifications_user_scope_non_follower_anonymous(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_require_current_user,
    ):
        """Test user scope with non-follower sends anonymous notification."""
        mock_require_current_user.return_value = self.regular_user
        # Setup mocks
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user
        # Sharer does NOT follow author - should be anonymous
        mock_user_client.validate_follower_relationship.return_value = False

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = self.service.send_recipe_shared_notifications(
            request=self.recipe_shared_request,
        )

        # Assertions - should still succeed
        self.assertEqual(response.queued_count, 2)
        self.assertEqual(len(response.notifications), 2)

        # Verify follower validation was called
        self.assertEqual(mock_user_client.validate_follower_relationship.call_count, 1)

        # Verify sharer details were NOT fetched (anonymous share)
        sharer_fetch_calls = [
            call
            for call in mock_user_client.get_user.call_args_list
            if call[0][0] == str(self.recipe_shared_request.sharer_id)
        ]
        self.assertEqual(len(sharer_fetch_calls), 0)

    @patch("core.services.recipe_notification_service.require_current_user")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    def test_send_notifications_without_sharer_id_anonymous(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_require_current_user,
    ):
        """Test notification without sharer_id is anonymous."""
        mock_require_current_user.return_value = self.admin_user

        # Create request without sharer_id
        request = RecipeSharedRequest(
            recipient_ids=[uuid4()],
            recipe_id=123,
            sharer_id=None,
            share_message="Check this out!",
        )

        # Setup mocks
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = self.service.send_recipe_shared_notifications(
            request=request,
        )

        # Assertions
        self.assertEqual(response.queued_count, 1)

        # Verify follower validation was NOT called (no sharer_id)
        mock_user_client.validate_follower_relationship.assert_not_called()

        # Verify metadata includes is_anonymous=True and sharer_id=None
        call_args = mock_notification_service.create_notification.call_args
        metadata = call_args[1]["metadata"]
        self.assertIs(metadata["is_anonymous"], True)
        self.assertIsNone(metadata["sharer_id"])

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
            recipe_id=int(self.recipe_shared_request.recipe_id)
        )

        # Execute and assert
        with self.assertRaises(RecipeNotFoundError):
            self.service.send_recipe_shared_notifications(
                request=self.recipe_shared_request,
            )

    @patch("core.services.recipe_notification_service.require_current_user")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    def test_send_notifications_sharer_not_found(
        self,
        mock_user_client,
        mock_recipe_client,
        mock_require_current_user,
    ):
        """Test sharer not found raises UserNotFoundError."""
        mock_require_current_user.return_value = self.admin_user
        # Setup mocks
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        # First call for sharer raises error
        mock_user_client.get_user.side_effect = UserNotFoundError(
            user_id=str(self.recipe_shared_request.sharer_id)
        )

        # Execute and assert
        with self.assertRaises(UserNotFoundError):
            self.service.send_recipe_shared_notifications(
                request=self.recipe_shared_request,
            )

    @patch("core.services.recipe_notification_service.require_current_user")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    @patch("core.services.recipe_notification_service.render_to_string")
    def test_send_notifications_renders_email_template_with_sharer(
        self,
        mock_render,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_require_current_user,
    ):
        """Test email template rendered with sharer identity."""
        mock_require_current_user.return_value = self.admin_user
        # Setup mocks
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user
        mock_render.return_value = "<html>Test email</html>"

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        self.service.send_recipe_shared_notifications(
            request=self.recipe_shared_request,
        )

        # Verify template was rendered
        self.assertEqual(mock_render.call_count, 2)
        first_call = mock_render.call_args_list[0]
        self.assertEqual(first_call[0][0], "emails/recipe_shared.html")
        context = first_call[0][1]
        self.assertIn("recipient_name", context)
        self.assertIn("recipe_title", context)
        self.assertIn("recipe_url", context)
        self.assertIn("sharer_name", context)
        self.assertIn("share_message", context)
        self.assertIn("is_anonymous", context)
        # Admin scope should reveal identity
        self.assertFalse(context["is_anonymous"])

    @patch("core.services.recipe_notification_service.require_current_user")
    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    @patch("core.services.recipe_notification_service.render_to_string")
    def test_send_notifications_renders_email_template_anonymous(
        self,
        mock_render,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        mock_require_current_user,
    ):
        """Test email template rendered for anonymous share."""
        mock_require_current_user.return_value = self.regular_user
        # Setup mocks
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user
        # Sharer not a follower - anonymous
        mock_user_client.validate_follower_relationship.return_value = False
        mock_render.return_value = "<html>Test email</html>"

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        self.service.send_recipe_shared_notifications(
            request=self.recipe_shared_request,
        )

        # Verify template was rendered
        self.assertEqual(mock_render.call_count, 2)
        first_call = mock_render.call_args_list[0]
        context = first_call[0][1]
        # Anonymous share
        self.assertTrue(context["is_anonymous"])
        self.assertIsNone(context["sharer_name"])

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
        self.service.send_recipe_shared_notifications(
            request=self.recipe_shared_request,
        )

        # Verify metadata was included in notification creation
        call_args = mock_notification_service.create_notification.call_args
        metadata = call_args[1]["metadata"]

        self.assertEqual(metadata["template_type"], "recipe_shared")
        self.assertEqual(
            metadata["recipe_id"], str(self.recipe_shared_request.recipe_id)
        )
        self.assertEqual(
            metadata["sharer_id"], str(self.recipe_shared_request.sharer_id)
        )
        self.assertIn("is_anonymous", metadata)
        self.assertEqual(
            metadata["share_message"], self.recipe_shared_request.share_message
        )

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
        self.service.send_recipe_shared_notifications(
            request=self.recipe_shared_request,
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
        request = RecipeSharedRequest(
            recipient_ids=[uuid4(), uuid4(), uuid4()],
            recipe_id=123,
            sharer_id=uuid4(),
            share_message="Amazing recipe!",
        )

        # Setup mocks
        mock_recipe_client.get_recipe.return_value = self.mock_recipe
        mock_user_client.get_user.return_value = self.mock_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = self.service.send_recipe_shared_notifications(
            request=request,
        )

        # Assertions
        self.assertEqual(response.queued_count, 3)
        self.assertEqual(len(response.notifications), 3)
        self.assertEqual(mock_notification_service.create_notification.call_count, 3)
