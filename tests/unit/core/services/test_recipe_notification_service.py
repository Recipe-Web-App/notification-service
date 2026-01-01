"""Tests for RecipeNotificationService with two-table schema."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

from django.db.models.signals import post_save

import pytest
from rest_framework.exceptions import PermissionDenied

from core.auth.oauth2 import OAuth2User
from core.exceptions import RecipeNotFoundError
from core.models.user import User
from core.schemas.notification import RecipePublishedRequest
from core.schemas.recipe import RecipeDto
from core.schemas.user import UserSearchResult
from core.services.recipe_notification_service import (
    recipe_notification_service,
)
from core.signals.user_signals import send_welcome_email


@pytest.fixture(autouse=True)
def disconnect_signals():
    """Disconnect signals for all tests."""
    post_save.disconnect(send_welcome_email, sender=User)
    yield
    post_save.connect(send_welcome_email, sender=User)


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user."""
    return OAuth2User(
        user_id=str(uuid4()),
        client_id="test-client",
        scopes=["notification:admin"],
    )


@pytest.fixture
def mock_regular_user():
    """Create a mock regular user."""
    return OAuth2User(
        user_id=str(uuid4()),
        client_id="test-client",
        scopes=["notification:user"],
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
def mock_user_dto():
    """Create a mock user DTO."""
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
def recipe_published_request():
    """Create a recipe published request."""
    return RecipePublishedRequest(
        recipient_ids=[uuid4(), uuid4()],
        recipe_id=123,
    )


@pytest.mark.django_db
@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.User.objects")
def test_send_notifications_admin_scope_success(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user_dto,
    recipe_published_request,
):
    """Test sending notifications with admin scope bypasses follower check."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    response = recipe_notification_service.send_recipe_published_notifications(
        request=recipe_published_request,
    )

    assert response.queued_count == 2
    assert len(response.notifications) == 2
    assert response.message == "Notifications queued successfully"

    mock_recipe_client.get_recipe.assert_called_once_with(
        int(recipe_published_request.recipe_id)
    )
    mock_user_client.validate_follower_relationship.assert_not_called()
    assert mock_notification_service.create_notification.call_count == 2


@pytest.mark.django_db
@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.User.objects")
def test_send_notifications_user_scope_with_valid_followers(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_regular_user,
    mock_recipe,
    mock_user_dto,
    recipe_published_request,
):
    """Test sending notifications with user scope validates followers."""
    mock_require_current_user.return_value = mock_regular_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_user_client.get_user.return_value = mock_user_dto
    mock_user_client.validate_follower_relationship.return_value = True

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    response = recipe_notification_service.send_recipe_published_notifications(
        request=recipe_published_request,
    )

    assert response.queued_count == 2
    assert len(response.notifications) == 2
    assert mock_user_client.validate_follower_relationship.call_count == 2


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
def test_send_notifications_recipe_not_found(
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    recipe_published_request,
):
    """Test recipe not found raises RecipeNotFoundError."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.side_effect = RecipeNotFoundError(
        recipe_id=int(recipe_published_request.recipe_id)
    )

    with pytest.raises(RecipeNotFoundError):
        recipe_notification_service.send_recipe_published_notifications(
            request=recipe_published_request,
        )


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
def test_send_notifications_invalid_follower_relationships(
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_regular_user,
    mock_recipe,
    recipe_published_request,
):
    """Test invalid follower relationships raises PermissionDenied."""
    mock_require_current_user.return_value = mock_regular_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_user_client.validate_follower_relationship.side_effect = [True, False]

    with pytest.raises(PermissionDenied) as exc_info:
        recipe_notification_service.send_recipe_published_notifications(
            request=recipe_published_request,
        )

    assert "not followers" in str(exc_info.value.detail).lower()


@pytest.mark.django_db
@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.User.objects")
def test_send_notifications_includes_notification_data(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user_dto,
    recipe_published_request,
):
    """Test notifications include correct notification_data."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    recipe_notification_service.send_recipe_published_notifications(
        request=recipe_published_request,
    )

    call_kwargs = mock_notification_service.create_notification.call_args[1]
    notification_data = call_kwargs["notification_data"]

    assert notification_data["recipe_id"] == str(recipe_published_request.recipe_id)
    assert "template_version" in notification_data


@pytest.mark.django_db
@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.User.objects")
def test_send_notifications_uses_correct_category(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user_dto,
    recipe_published_request,
):
    """Test notification uses correct category."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    recipe_notification_service.send_recipe_published_notifications(
        request=recipe_published_request,
    )

    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["notification_category"] == "RECIPE_PUBLISHED"
