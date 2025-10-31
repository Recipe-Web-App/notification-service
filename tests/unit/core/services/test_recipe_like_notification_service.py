"""Tests for RecipeNotificationService recipe-liked functionality."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from rest_framework.exceptions import PermissionDenied

from core.auth.oauth2 import OAuth2User
from core.exceptions import RecipeNotFoundError
from core.schemas.notification import RecipeLikedRequest
from core.schemas.recipe import RecipeDto
from core.schemas.user import UserSearchResult
from core.services.recipe_notification_service import (
    RecipeNotificationService,
)


@pytest.mark.django_db
class TestRecipeLikedNotifications:
    """Test suite for recipe-liked notifications."""

    @pytest.fixture
    def service(self):
        """Create RecipeNotificationService instance."""
        return RecipeNotificationService()

    @pytest.fixture
    def admin_user(self):
        """Create admin OAuth2 user."""
        return OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:admin"],
        )

    @pytest.fixture
    def regular_user(self):
        """Create regular OAuth2 user with notification:user scope."""
        return OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:user"],
        )

    @pytest.fixture
    def recipe_liked_request(self):
        """Create recipe liked request."""
        return RecipeLikedRequest(
            recipient_ids=[uuid4(), uuid4()],
            recipe_id=uuid4(),
            liker_id=uuid4(),
        )

    @pytest.fixture
    def mock_recipe(self):
        """Create mock recipe."""
        return RecipeDto(
            recipe_id=123,
            user_id=uuid4(),
            title="Test Recipe",
            servings=Decimal("4"),
            created_at="2025-10-29T12:00:00Z",
        )

    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        return UserSearchResult(
            user_id=uuid4(),
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    def test_send_notifications_admin_scope_success(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        service,
        admin_user,
        recipe_liked_request,
        mock_recipe,
        mock_user,
    ):
        """Test sending notifications with admin scope bypasses follower check."""
        # Setup mocks
        mock_recipe_client.get_recipe.return_value = mock_recipe
        mock_user_client.get_user.return_value = mock_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = service.send_recipe_liked_notifications(
            request=recipe_liked_request,
            authenticated_user=admin_user,
        )

        # Assertions
        assert response.queued_count == 2
        assert len(response.notifications) == 2
        assert response.message == "Notifications queued successfully"

        # Verify recipe was fetched
        mock_recipe_client.get_recipe.assert_called_once_with(
            int(recipe_liked_request.recipe_id)
        )

        # Verify follower validation was NOT called (admin bypass)
        mock_user_client.validate_follower_relationship.assert_not_called()

        # Verify notification service called for each recipient
        assert mock_notification_service.create_notification.call_count == 2

    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    def test_send_notifications_user_scope_with_valid_follower(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        service,
        regular_user,
        recipe_liked_request,
        mock_recipe,
        mock_user,
    ):
        """Test sending notifications with user scope validates liker follows author."""
        # Setup mocks
        mock_recipe_client.get_recipe.return_value = mock_recipe
        mock_user_client.get_user.return_value = mock_user
        # Liker is a valid follower of the author
        mock_user_client.validate_follower_relationship.return_value = True

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = service.send_recipe_liked_notifications(
            request=recipe_liked_request,
            authenticated_user=regular_user,
        )

        # Assertions
        assert response.queued_count == 2
        assert len(response.notifications) == 2

        # Verify follower validation was called once (for liker)
        assert mock_user_client.validate_follower_relationship.call_count == 1

    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    def test_send_notifications_recipe_not_found(
        self,
        mock_recipe_client,
        service,
        admin_user,
        recipe_liked_request,
    ):
        """Test recipe not found raises RecipeNotFoundError."""
        # Setup mock to raise RecipeNotFoundError
        mock_recipe_client.get_recipe.side_effect = RecipeNotFoundError(
            recipe_id=int(recipe_liked_request.recipe_id)
        )

        # Execute and assert
        with pytest.raises(RecipeNotFoundError):
            service.send_recipe_liked_notifications(
                request=recipe_liked_request,
                authenticated_user=admin_user,
            )

    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    def test_send_notifications_invalid_follower_relationship(
        self,
        mock_user_client,
        mock_recipe_client,
        service,
        regular_user,
        recipe_liked_request,
        mock_recipe,
    ):
        """Test liker not following author raises PermissionDenied."""
        # Setup mocks
        mock_recipe_client.get_recipe.return_value = mock_recipe
        # Liker is not a follower of the author
        mock_user_client.validate_follower_relationship.return_value = False

        # Execute and assert
        with pytest.raises(PermissionDenied) as exc_info:
            service.send_recipe_liked_notifications(
                request=recipe_liked_request,
                authenticated_user=regular_user,
            )

        assert "not a follower" in str(exc_info.value.detail).lower()

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
        service,
        admin_user,
        recipe_liked_request,
        mock_recipe,
        mock_user,
    ):
        """Test email template is rendered with correct context."""
        # Setup mocks
        mock_recipe_client.get_recipe.return_value = mock_recipe
        mock_user_client.get_user.return_value = mock_user
        mock_render.return_value = "<html>Test email</html>"

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        service.send_recipe_liked_notifications(
            request=recipe_liked_request,
            authenticated_user=admin_user,
        )

        # Verify template was rendered
        assert mock_render.call_count == 2
        first_call = mock_render.call_args_list[0]
        assert first_call[0][0] == "emails/recipe_liked.html"
        assert "recipient_name" in first_call[0][1]
        assert "liker_name" in first_call[0][1]
        assert "recipe_title" in first_call[0][1]
        assert "recipe_url" in first_call[0][1]

    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    def test_send_notifications_includes_metadata(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        service,
        admin_user,
        recipe_liked_request,
        mock_recipe,
        mock_user,
    ):
        """Test notifications include correct metadata."""
        # Setup mocks
        mock_recipe_client.get_recipe.return_value = mock_recipe
        mock_user_client.get_user.return_value = mock_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        service.send_recipe_liked_notifications(
            request=recipe_liked_request,
            authenticated_user=admin_user,
        )

        # Verify metadata was included in notification creation
        call_args = mock_notification_service.create_notification.call_args
        metadata = call_args[1]["metadata"]

        assert metadata["template_type"] == "recipe_liked"
        assert metadata["recipe_id"] == str(recipe_liked_request.recipe_id)
        assert metadata["liker_id"] == str(recipe_liked_request.liker_id)

    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    def test_send_notifications_queue_flag_enabled(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        service,
        admin_user,
        recipe_liked_request,
        mock_recipe,
        mock_user,
    ):
        """Test notifications are queued for async processing."""
        # Setup mocks
        mock_recipe_client.get_recipe.return_value = mock_recipe
        mock_user_client.get_user.return_value = mock_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        service.send_recipe_liked_notifications(
            request=recipe_liked_request,
            authenticated_user=admin_user,
        )

        # Verify queue flag was set to True
        call_args = mock_notification_service.create_notification.call_args
        assert call_args[1]["auto_queue"] is True

    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    @patch("core.services.recipe_notification_service.user_client")
    @patch("core.services.recipe_notification_service.notification_service")
    def test_send_notifications_multiple_recipients(
        self,
        mock_notification_service,
        mock_user_client,
        mock_recipe_client,
        service,
        admin_user,
        mock_recipe,
        mock_user,
    ):
        """Test handling multiple recipients correctly."""
        # Create request with 3 recipients
        request = RecipeLikedRequest(
            recipient_ids=[uuid4(), uuid4(), uuid4()],
            recipe_id=uuid4(),
            liker_id=uuid4(),
        )

        # Setup mocks
        mock_recipe_client.get_recipe.return_value = mock_recipe
        mock_user_client.get_user.return_value = mock_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = service.send_recipe_liked_notifications(
            request=request,
            authenticated_user=admin_user,
        )

        # Assertions
        assert response.queued_count == 3
        assert len(response.notifications) == 3
        assert mock_notification_service.create_notification.call_count == 3
