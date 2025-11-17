"""Unit tests for recipe featured notification service."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from core.auth.oauth2 import OAuth2User
from core.exceptions import RecipeNotFoundError
from core.schemas.notification import RecipeFeaturedRequest
from core.schemas.recipe import RecipeDto
from core.schemas.user import UserSearchResult
from core.services.recipe_notification_service import (
    recipe_notification_service,
)


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user."""
    return OAuth2User(
        user_id=str(uuid4()),
        client_id="test-client",
        scopes=["notification:admin"],
    )


@pytest.fixture
def mock_recipe():
    """Create a mock recipe."""
    return RecipeDto(
        recipe_id=123,
        user_id=uuid4(),
        title="Test Recipe",
        servings=Decimal("4"),
        created_at="2025-10-29T12:00:00Z",
    )


@pytest.fixture
def mock_user():
    """Create a mock user."""
    return UserSearchResult(
        user_id=uuid4(),
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def recipe_featured_request():
    """Create a recipe featured request."""
    return RecipeFeaturedRequest(
        recipient_ids=[uuid4()],
        recipe_id=123,
        featured_reason="Editor's Choice",
    )


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
def test_send_recipe_featured_notifications_sends_successfully(
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user,
    recipe_featured_request,
):
    """Test recipe featured notifications are sent successfully."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    result = recipe_notification_service.send_recipe_featured_notifications(
        recipe_featured_request
    )

    # Assert
    assert result.queued_count == 1
    assert len(result.notifications) == 1
    mock_notification_service.create_notification.assert_called_once()


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
def test_send_recipe_featured_notifications_raises_error_for_nonexistent_recipe(
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    recipe_featured_request,
):
    """Test RecipeNotFoundError is raised for nonexistent recipe."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.side_effect = RecipeNotFoundError(recipe_id=123)

    # Execute & Assert
    with pytest.raises(RecipeNotFoundError):
        recipe_notification_service.send_recipe_featured_notifications(
            recipe_featured_request
        )


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
def test_send_recipe_featured_notifications_includes_featured_reason_in_metadata(
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user,
    recipe_featured_request,
):
    """Test notification metadata includes featured_reason."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    recipe_notification_service.send_recipe_featured_notifications(
        recipe_featured_request
    )

    # Assert
    call_kwargs = mock_notification_service.create_notification.call_args[1]
    metadata = call_kwargs["metadata"]

    assert metadata["template_type"] == "recipe_featured"
    assert metadata["recipe_id"] == str(recipe_featured_request.recipe_id)
    assert metadata["featured_reason"] == "Editor's Choice"
    assert "recipient_id" in metadata


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.render_to_string")
def test_send_recipe_featured_notifications_renders_email_template(
    mock_render,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user,
    recipe_featured_request,
):
    """Test email template is rendered with correct context."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    mock_render.return_value = "<html>email content</html>"

    # Execute
    recipe_notification_service.send_recipe_featured_notifications(
        recipe_featured_request
    )

    # Assert
    mock_render.assert_called_once()
    call_args = mock_render.call_args[0]

    assert call_args[0] == "emails/recipe_featured.html"
    context = call_args[1]

    assert "recipe_title" in context
    assert "featured_reason" in context
    assert "recipe_url" in context
    assert context["featured_reason"] == "Editor's Choice"


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
def test_send_recipe_featured_notifications_auto_queue_enabled(
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user,
    recipe_featured_request,
):
    """Test notifications are queued for async processing."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    recipe_notification_service.send_recipe_featured_notifications(
        recipe_featured_request
    )

    # Assert
    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["auto_queue"] is True


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
def test_send_recipe_featured_notifications_handles_multiple_recipients(
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user,
):
    """Test multiple recipients receive notifications."""
    # Setup
    request = RecipeFeaturedRequest(
        recipient_ids=[uuid4(), uuid4(), uuid4()],
        recipe_id=123,
        featured_reason="Top Rated",
    )

    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    result = recipe_notification_service.send_recipe_featured_notifications(request)

    # Assert
    assert result.queued_count == 3
    assert len(result.notifications) == 3
    assert mock_notification_service.create_notification.call_count == 3


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
def test_send_recipe_featured_notifications_without_featured_reason(
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user,
):
    """Test notification works without featured_reason (optional field)."""
    # Setup
    request = RecipeFeaturedRequest(
        recipient_ids=[uuid4()],
        recipe_id=123,
        # No featured_reason provided
    )

    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    result = recipe_notification_service.send_recipe_featured_notifications(request)

    # Assert
    assert result.queued_count == 1

    # Verify metadata has None for featured_reason
    call_kwargs = mock_notification_service.create_notification.call_args[1]
    metadata = call_kwargs["metadata"]
    assert metadata["featured_reason"] is None
