"""Tests for RecipeNotificationService recipe-commented functionality."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from rest_framework.exceptions import PermissionDenied

from core.auth.oauth2 import OAuth2User
from core.exceptions import CommentNotFoundError, RecipeNotFoundError
from core.schemas.notification import RecipeCommentedRequest
from core.schemas.recipe import CommentDto, RecipeDto
from core.schemas.user import UserSearchResult
from core.services.recipe_notification_service import (
    RecipeNotificationService,
)


@pytest.mark.django_db
class TestRecipeCommentedNotifications:
    """Test suite for recipe-commented notifications."""

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
    def recipe_commented_request(self):
        """Create recipe commented request."""
        return RecipeCommentedRequest(
            recipient_ids=[uuid4(), uuid4()],
            comment_id=uuid4(),
        )

    @pytest.fixture
    def mock_comment(self):
        """Create mock comment."""
        return CommentDto(
            comment_id=uuid4(),
            recipe_id=123,
            user_id=uuid4(),
            comment_text="This recipe looks delicious! I can't wait to try it.",
            created_at=datetime.now(UTC),
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
        recipe_commented_request,
        mock_comment,
        mock_recipe,
        mock_user,
    ):
        """Test sending notifications with admin scope bypasses follower check."""
        # Setup mocks
        mock_recipe_client.get_comment.return_value = mock_comment
        mock_recipe_client.get_recipe.return_value = mock_recipe
        mock_user_client.get_user.return_value = mock_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = service.send_recipe_commented_notifications(
            request=recipe_commented_request,
            authenticated_user=admin_user,
        )

        # Assertions
        assert response.queued_count == 2
        assert len(response.notifications) == 2
        assert response.message == "Notifications queued successfully"

        # Verify comment was fetched
        mock_recipe_client.get_comment.assert_called_once_with(
            str(recipe_commented_request.comment_id)
        )

        # Verify recipe was fetched
        mock_recipe_client.get_recipe.assert_called_once_with(mock_comment.recipe_id)

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
        recipe_commented_request,
        mock_comment,
        mock_recipe,
        mock_user,
    ):
        """Test user scope validates commenter follows author."""
        # Setup mocks
        mock_recipe_client.get_comment.return_value = mock_comment
        mock_recipe_client.get_recipe.return_value = mock_recipe
        mock_user_client.get_user.return_value = mock_user
        # Commenter is a valid follower of the author
        mock_user_client.validate_follower_relationship.return_value = True

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        response = service.send_recipe_commented_notifications(
            request=recipe_commented_request,
            authenticated_user=regular_user,
        )

        # Assertions
        assert response.queued_count == 2
        assert len(response.notifications) == 2

        # Verify follower validation was called once (for commenter)
        assert mock_user_client.validate_follower_relationship.call_count == 1

    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    def test_send_notifications_comment_not_found(
        self,
        mock_recipe_client,
        service,
        admin_user,
        recipe_commented_request,
    ):
        """Test comment not found raises CommentNotFoundError."""
        # Setup mock to raise CommentNotFoundError
        mock_recipe_client.get_comment.side_effect = CommentNotFoundError(
            comment_id=str(recipe_commented_request.comment_id)
        )

        # Execute and assert
        with pytest.raises(CommentNotFoundError):
            service.send_recipe_commented_notifications(
                request=recipe_commented_request,
                authenticated_user=admin_user,
            )

    @patch("core.services.recipe_notification_service.recipe_management_service_client")
    def test_send_notifications_recipe_not_found(
        self,
        mock_recipe_client,
        service,
        admin_user,
        recipe_commented_request,
        mock_comment,
    ):
        """Test recipe not found raises RecipeNotFoundError."""
        # Setup mocks
        mock_recipe_client.get_comment.return_value = mock_comment
        # Recipe not found after fetching comment
        mock_recipe_client.get_recipe.side_effect = RecipeNotFoundError(
            recipe_id=mock_comment.recipe_id
        )

        # Execute and assert
        with pytest.raises(RecipeNotFoundError):
            service.send_recipe_commented_notifications(
                request=recipe_commented_request,
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
        recipe_commented_request,
        mock_comment,
        mock_recipe,
    ):
        """Test commenter not following author raises PermissionDenied."""
        # Setup mocks
        mock_recipe_client.get_comment.return_value = mock_comment
        mock_recipe_client.get_recipe.return_value = mock_recipe
        # Commenter is not a follower of the author
        mock_user_client.validate_follower_relationship.return_value = False

        # Execute and assert
        with pytest.raises(PermissionDenied) as exc_info:
            service.send_recipe_commented_notifications(
                request=recipe_commented_request,
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
        recipe_commented_request,
        mock_comment,
        mock_recipe,
        mock_user,
    ):
        """Test email template rendered with context including comment preview."""
        # Setup mocks
        mock_recipe_client.get_comment.return_value = mock_comment
        mock_recipe_client.get_recipe.return_value = mock_recipe
        mock_user_client.get_user.return_value = mock_user
        mock_render.return_value = "<html>Test email</html>"

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        service.send_recipe_commented_notifications(
            request=recipe_commented_request,
            authenticated_user=admin_user,
        )

        # Verify template was rendered
        assert mock_render.call_count == 2
        first_call = mock_render.call_args_list[0]
        assert first_call[0][0] == "emails/recipe_commented.html"
        assert "recipient_name" in first_call[0][1]
        assert "commenter_name" in first_call[0][1]
        assert "recipe_title" in first_call[0][1]
        assert "comment_preview" in first_call[0][1]
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
        recipe_commented_request,
        mock_comment,
        mock_recipe,
        mock_user,
    ):
        """Test notifications include correct metadata."""
        # Setup mocks
        mock_recipe_client.get_comment.return_value = mock_comment
        mock_recipe_client.get_recipe.return_value = mock_recipe
        mock_user_client.get_user.return_value = mock_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        service.send_recipe_commented_notifications(
            request=recipe_commented_request,
            authenticated_user=admin_user,
        )

        # Verify metadata was included in notification creation
        call_args = mock_notification_service.create_notification.call_args
        metadata = call_args[1]["metadata"]

        assert metadata["template_type"] == "recipe_commented"
        assert metadata["comment_id"] == str(recipe_commented_request.comment_id)
        assert metadata["recipe_id"] == str(mock_comment.recipe_id)
        assert metadata["commenter_id"] == str(mock_comment.user_id)

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
        recipe_commented_request,
        mock_comment,
        mock_recipe,
        mock_user,
    ):
        """Test notifications are queued for async processing."""
        # Setup mocks
        mock_recipe_client.get_comment.return_value = mock_comment
        mock_recipe_client.get_recipe.return_value = mock_recipe
        mock_user_client.get_user.return_value = mock_user

        mock_notification = Mock()
        mock_notification.notification_id = uuid4()
        mock_notification_service.create_notification.return_value = mock_notification

        # Execute
        service.send_recipe_commented_notifications(
            request=recipe_commented_request,
            authenticated_user=admin_user,
        )

        # Verify queue flag was set to True
        call_args = mock_notification_service.create_notification.call_args
        assert call_args[1]["auto_queue"] is True
