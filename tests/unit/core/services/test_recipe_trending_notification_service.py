"""Unit tests for recipe trending notification service."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from core.auth.oauth2 import OAuth2User
from core.exceptions import RecipeNotFoundError
from core.schemas.notification import RecipeTrendingRequest
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
def recipe_trending_request():
    """Create a recipe trending request."""
    return RecipeTrendingRequest(
        recipient_ids=[uuid4()],
        recipe_id=123,
        trending_metrics="1,234 views and 89 likes in the past 24 hours",
    )


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
def test_send_recipe_trending_notifications_sends_successfully(
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user,
    recipe_trending_request,
):
    """Test recipe trending notifications are sent successfully."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    result = recipe_notification_service.send_recipe_trending_notifications(
        recipe_trending_request
    )

    # Assert
    assert result.queued_count == 1
    assert len(result.notifications) == 1
    mock_notification_service.create_notification.assert_called_once()


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
def test_send_recipe_trending_notifications_raises_error_for_nonexistent_recipe(
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    recipe_trending_request,
):
    """Test RecipeNotFoundError is raised for nonexistent recipe."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.side_effect = RecipeNotFoundError(recipe_id=123)

    # Execute & Assert
    with pytest.raises(RecipeNotFoundError):
        recipe_notification_service.send_recipe_trending_notifications(
            recipe_trending_request
        )


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
def test_send_recipe_trending_notifications_includes_trending_metrics_in_metadata(
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user,
    recipe_trending_request,
):
    """Test notification metadata includes trending_metrics."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    recipe_notification_service.send_recipe_trending_notifications(
        recipe_trending_request
    )

    # Assert
    call_kwargs = mock_notification_service.create_notification.call_args[1]
    metadata = call_kwargs["metadata"]

    assert metadata["template_type"] == "recipe_trending"
    assert metadata["recipe_id"] == str(recipe_trending_request.recipe_id)
    assert (
        metadata["trending_metrics"] == "1,234 views and 89 likes in the past 24 hours"
    )
    assert "recipient_id" in metadata


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.render_to_string")
def test_send_recipe_trending_notifications_renders_email_template(
    mock_render,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user,
    recipe_trending_request,
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
    recipe_notification_service.send_recipe_trending_notifications(
        recipe_trending_request
    )

    # Assert
    mock_render.assert_called_once()
    call_args = mock_render.call_args[0]

    assert call_args[0] == "emails/recipe_trending.html"
    context = call_args[1]

    assert "recipe_title" in context
    assert "trending_metrics" in context
    assert "recipe_url" in context
    assert (
        context["trending_metrics"] == "1,234 views and 89 likes in the past 24 hours"
    )


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
def test_send_recipe_trending_notifications_auto_queue_enabled(
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user,
    recipe_trending_request,
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
    recipe_notification_service.send_recipe_trending_notifications(
        recipe_trending_request
    )

    # Assert
    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["auto_queue"] is True


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
def test_send_recipe_trending_notifications_handles_multiple_recipients(
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
    request = RecipeTrendingRequest(
        recipient_ids=[uuid4(), uuid4(), uuid4()],
        recipe_id=123,
        trending_metrics="500 views in the last hour",
    )

    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    result = recipe_notification_service.send_recipe_trending_notifications(request)

    # Assert
    assert result.queued_count == 3
    assert len(result.notifications) == 3
    assert mock_notification_service.create_notification.call_count == 3


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
def test_send_recipe_trending_notifications_without_trending_metrics(
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user,
):
    """Test notification works without trending_metrics (optional field)."""
    # Setup
    request = RecipeTrendingRequest(
        recipient_ids=[uuid4()],
        recipe_id=123,
        # No trending_metrics provided
    )

    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    result = recipe_notification_service.send_recipe_trending_notifications(request)

    # Assert
    assert result.queued_count == 1

    # Verify metadata has None for trending_metrics
    call_kwargs = mock_notification_service.create_notification.call_args[1]
    metadata = call_kwargs["metadata"]
    assert metadata["trending_metrics"] is None
