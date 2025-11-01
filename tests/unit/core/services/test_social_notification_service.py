"""Tests for SocialNotificationService."""

from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import TestCase

from rest_framework.exceptions import PermissionDenied

from core.auth.oauth2 import OAuth2User
from core.exceptions import UserNotFoundError
from core.schemas.notification import NewFollowerRequest
from core.schemas.user import UserSearchResult
from core.services.social_notification_service import SocialNotificationService


class TestSocialNotificationService(TestCase):
    """Test suite for SocialNotificationService."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = SocialNotificationService()

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

        self.follower_id = uuid4()
        self.recipient_id = uuid4()

        self.new_follower_request = NewFollowerRequest(
            follower_id=self.follower_id,
            recipient_ids=[self.recipient_id],
        )

        self.mock_follower = UserSearchResult(
            user_id=self.follower_id,
            username="newfollower",
            email="follower@example.com",
            full_name="New Follower",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        self.mock_recipient = UserSearchResult(
            user_id=self.recipient_id,
            username="recipient",
            email="recipient@example.com",
            full_name="Recipient User",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @patch("core.services.social_notification_service.user_client")
    @patch("core.services.social_notification_service.recipe_management_service_client")
    @patch("core.services.social_notification_service.notification_service")
    def test_send_notifications_admin_scope_success(
        self,
        mock_notification_service,
        mock_recipe_client,
        mock_user_client,
    ):
        """Test sending notifications with admin scope succeeds."""
        # Setup mocks
        mock_user_client.get_user.side_effect = [
            self.mock_follower,
            self.mock_recipient,
        ]
        mock_user_client.validate_follower_relationship.return_value = True
        mock_recipe_client.get_user_recipe_count.return_value = 5

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = self.service.send_new_follower_notifications(
            request=self.new_follower_request,
            authenticated_user=self.admin_user,
        )

        # Assertions
        self.assertEqual(response.queued_count, 1)
        self.assertEqual(len(response.notifications), 1)
        self.assertEqual(response.message, "Notifications queued successfully")

        # Verify follower was fetched
        self.assertEqual(mock_user_client.get_user.call_count, 2)
        mock_user_client.get_user.assert_any_call(str(self.follower_id))
        mock_user_client.get_user.assert_any_call(str(self.recipient_id))

        # Verify follower relationship was validated
        mock_user_client.validate_follower_relationship.assert_called_once_with(
            follower_id=str(self.follower_id),
            followee_id=str(self.recipient_id),
        )

        # Verify recipe count was fetched
        mock_recipe_client.get_user_recipe_count.assert_called_once_with(
            str(self.follower_id)
        )

        # Verify notification service called
        mock_notification_service.create_notification.assert_called_once()

    def test_send_notifications_without_admin_scope_raises_permission_denied(self):
        """Test sending notifications without admin scope raises PermissionDenied."""
        # Execute and assert
        with self.assertRaises(PermissionDenied) as exc_info:
            self.service.send_new_follower_notifications(
                request=self.new_follower_request,
                authenticated_user=self.regular_user,
            )

        self.assertIn("notification:admin", str(exc_info.exception.detail))

    @patch("core.services.social_notification_service.user_client")
    def test_send_notifications_follower_not_found(
        self,
        mock_user_client,
    ):
        """Test follower not found raises UserNotFoundError."""
        # Setup mock to raise UserNotFoundError
        mock_user_client.get_user.side_effect = UserNotFoundError(
            user_id=str(self.follower_id)
        )

        # Execute and assert
        with self.assertRaises(UserNotFoundError):
            self.service.send_new_follower_notifications(
                request=self.new_follower_request,
                authenticated_user=self.admin_user,
            )

    @patch("core.services.social_notification_service.user_client")
    @patch("core.services.social_notification_service.recipe_management_service_client")
    def test_send_notifications_recipient_not_found(
        self,
        mock_recipe_client,
        mock_user_client,
    ):
        """Test recipient not found raises UserNotFoundError."""
        # Setup mocks - follower exists, relationship valid, recipient doesn't
        mock_user_client.get_user.side_effect = [
            self.mock_follower,  # First call for follower
            UserNotFoundError(user_id=str(self.recipient_id)),  # Second call fails
        ]
        mock_user_client.validate_follower_relationship.return_value = True
        mock_recipe_client.get_user_recipe_count.return_value = 5

        # Execute and assert
        with self.assertRaises(UserNotFoundError):
            self.service.send_new_follower_notifications(
                request=self.new_follower_request,
                authenticated_user=self.admin_user,
            )

    @patch("core.services.social_notification_service.user_client")
    def test_send_notifications_invalid_relationship_raises_permission_denied(
        self,
        mock_user_client,
    ):
        """Test invalid follower relationship raises PermissionDenied."""
        # Setup mocks
        mock_user_client.get_user.return_value = self.mock_follower
        mock_user_client.validate_follower_relationship.return_value = False

        # Execute and assert
        with self.assertRaises(PermissionDenied) as exc_info:
            self.service.send_new_follower_notifications(
                request=self.new_follower_request,
                authenticated_user=self.admin_user,
            )

        self.assertIn("does not exist", str(exc_info.exception.detail))

    @patch("core.services.social_notification_service.user_client")
    @patch("core.services.social_notification_service.recipe_management_service_client")
    @patch("core.services.social_notification_service.notification_service")
    @patch("core.services.social_notification_service.render_to_string")
    def test_send_notifications_renders_email_template(
        self,
        mock_render,
        mock_notification_service,
        mock_recipe_client,
        mock_user_client,
    ):
        """Test email template is rendered with correct context."""
        # Setup mocks
        mock_user_client.get_user.side_effect = [
            self.mock_follower,
            self.mock_recipient,
        ]
        mock_user_client.validate_follower_relationship.return_value = True
        mock_recipe_client.get_user_recipe_count.return_value = 10
        mock_render.return_value = "<html>Test email</html>"

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        self.service.send_new_follower_notifications(
            request=self.new_follower_request,
            authenticated_user=self.admin_user,
        )

        # Assertions - verify template was rendered with correct context
        mock_render.assert_called_once()
        call_args = mock_render.call_args
        self.assertEqual(call_args[0][0], "emails/new_follower.html")

        # Verify template context
        context = call_args[0][1]
        self.assertEqual(context["follower_name"], self.mock_follower.full_name)
        self.assertEqual(context["follower_username"], self.mock_follower.username)
        self.assertEqual(context["recipient_name"], self.mock_recipient.full_name)
        self.assertEqual(context["recipe_count"], 10)
        self.assertIn("/users/newfollower", context["profile_url"])
        self.assertIn("/users/newfollower/recipes", context["recipes_url"])

    @patch("core.services.social_notification_service.user_client")
    @patch("core.services.social_notification_service.recipe_management_service_client")
    @patch("core.services.social_notification_service.notification_service")
    def test_send_notifications_creates_correct_metadata(
        self,
        mock_notification_service,
        mock_recipe_client,
        mock_user_client,
    ):
        """Test notification is created with correct metadata."""
        # Setup mocks
        mock_user_client.get_user.side_effect = [
            self.mock_follower,
            self.mock_recipient,
        ]
        mock_user_client.validate_follower_relationship.return_value = True
        mock_recipe_client.get_user_recipe_count.return_value = 3

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        self.service.send_new_follower_notifications(
            request=self.new_follower_request,
            authenticated_user=self.admin_user,
        )

        # Assertions - verify notification was created with correct metadata
        mock_notification_service.create_notification.assert_called_once()
        call_args = mock_notification_service.create_notification.call_args

        # Verify email details
        self.assertEqual(call_args[1]["recipient_email"], self.mock_recipient.email)
        self.assertIn("following you", call_args[1]["subject"])
        self.assertEqual(call_args[1]["notification_type"], "email")
        self.assertTrue(call_args[1]["auto_queue"])

        # Verify metadata
        metadata = call_args[1]["metadata"]
        self.assertEqual(metadata["template_type"], "new_follower")
        self.assertEqual(metadata["follower_id"], str(self.follower_id))
        self.assertEqual(metadata["recipient_id"], str(self.recipient_id))

    @patch("core.services.social_notification_service.user_client")
    @patch("core.services.social_notification_service.recipe_management_service_client")
    @patch("core.services.social_notification_service.notification_service")
    def test_send_notifications_handles_zero_recipes(
        self,
        mock_notification_service,
        mock_recipe_client,
        mock_user_client,
    ):
        """Test notification is sent even when follower has zero recipes."""
        # Setup mocks
        mock_user_client.get_user.side_effect = [
            self.mock_follower,
            self.mock_recipient,
        ]
        mock_user_client.validate_follower_relationship.return_value = True
        mock_recipe_client.get_user_recipe_count.return_value = 0

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = self.service.send_new_follower_notifications(
            request=self.new_follower_request,
            authenticated_user=self.admin_user,
        )

        # Assertions
        self.assertEqual(response.queued_count, 1)
        mock_notification_service.create_notification.assert_called_once()

    @patch("core.services.social_notification_service.user_client")
    @patch("core.services.social_notification_service.recipe_management_service_client")
    @patch("core.services.social_notification_service.notification_service")
    def test_send_notifications_multiple_recipients(
        self,
        mock_notification_service,
        mock_recipe_client,
        mock_user_client,
    ):
        """Test sending notifications to multiple recipients."""
        # Setup request with multiple recipients
        recipient_ids = [uuid4(), uuid4()]
        request = NewFollowerRequest(
            follower_id=self.follower_id,
            recipient_ids=recipient_ids,
        )

        # Setup mocks
        mock_user_client.get_user.side_effect = [
            self.mock_follower,  # First call for follower
            self.mock_recipient,  # Recipients
            self.mock_recipient,
        ]
        mock_user_client.validate_follower_relationship.return_value = True
        mock_recipe_client.get_user_recipe_count.return_value = 5

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = self.service.send_new_follower_notifications(
            request=request,
            authenticated_user=self.admin_user,
        )

        # Assertions
        self.assertEqual(response.queued_count, 2)
        self.assertEqual(len(response.notifications), 2)

        # Verify relationship validated for each recipient
        self.assertEqual(mock_user_client.validate_follower_relationship.call_count, 2)

        # Verify notification created for each recipient
        self.assertEqual(mock_notification_service.create_notification.call_count, 2)
