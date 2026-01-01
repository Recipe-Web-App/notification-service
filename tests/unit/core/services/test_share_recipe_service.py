"""Tests for RecipeNotificationService share-recipe with two-table schema."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

from django.db.models.signals import post_save

import pytest

from core.auth.oauth2 import OAuth2User
from core.exceptions import RecipeNotFoundError, UserNotFoundError
from core.models.user import User
from core.schemas.notification import ShareRecipeRequest
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
    """Create a mock user DTO for downstream client."""
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
def share_recipe_request():
    """Create a share recipe request."""
    return ShareRecipeRequest(
        recipient_ids=[uuid4(), uuid4()],
        recipe_id=123,
        sharer_id=uuid4(),
        share_message="Check out this amazing recipe!",
    )


@pytest.mark.django_db
@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.media_management_service_client")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.User.objects")
def test_send_notifications_admin_scope_reveals_sharer(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_media_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user_dto,
    share_recipe_request,
):
    """Test admin scope always reveals sharer identity."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_media_client.get_recipe_media_ids.return_value = []
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    response = recipe_notification_service.share_recipe_with_users(
        request=share_recipe_request,
    )

    assert response.queued_count == 3
    assert len(response.notifications) == 3
    assert response.message == "Notifications queued successfully"

    # Verify recipe was fetched
    mock_recipe_client.get_recipe.assert_called_once_with(
        int(share_recipe_request.recipe_id)
    )

    # Verify follower validation was NOT called (admin bypass)
    mock_user_client.validate_follower_relationship.assert_not_called()

    # Verify sharer details were fetched (identity revealed)
    sharer_fetch_calls = [
        call
        for call in mock_user_client.get_user.call_args_list
        if call[0][0] == str(share_recipe_request.sharer_id)
    ]
    assert len(sharer_fetch_calls) == 1

    # Verify notification service called for each recipient
    assert mock_notification_service.create_notification.call_count == 3


@pytest.mark.django_db
@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.media_management_service_client")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.User.objects")
def test_send_notifications_user_scope_follower_reveals_sharer(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_media_client,
    mock_require_current_user,
    mock_regular_user,
    mock_recipe,
    mock_user_dto,
    share_recipe_request,
):
    """Test user scope with follower reveals sharer identity."""
    mock_require_current_user.return_value = mock_regular_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_media_client.get_recipe_media_ids.return_value = []
    mock_user_client.get_user.return_value = mock_user_dto
    mock_user_client.validate_follower_relationship.return_value = True

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    response = recipe_notification_service.share_recipe_with_users(
        request=share_recipe_request,
    )

    assert response.queued_count == 3
    assert len(response.notifications) == 3

    # Verify follower validation was called
    assert mock_user_client.validate_follower_relationship.call_count == 1

    # Verify sharer details were fetched (identity revealed)
    sharer_fetch_calls = [
        call
        for call in mock_user_client.get_user.call_args_list
        if call[0][0] == str(share_recipe_request.sharer_id)
    ]
    assert len(sharer_fetch_calls) == 1


@pytest.mark.django_db
@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.media_management_service_client")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.User.objects")
def test_send_notifications_user_scope_non_follower_anonymous(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_media_client,
    mock_require_current_user,
    mock_regular_user,
    mock_recipe,
    mock_user_dto,
    share_recipe_request,
):
    """Test user scope with non-follower sends anonymous notification."""
    mock_require_current_user.return_value = mock_regular_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_media_client.get_recipe_media_ids.return_value = []
    mock_user_client.get_user.return_value = mock_user_dto
    mock_user_client.validate_follower_relationship.return_value = False

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    response = recipe_notification_service.share_recipe_with_users(
        request=share_recipe_request,
    )

    assert response.queued_count == 3
    assert len(response.notifications) == 3

    # Verify follower validation was called
    assert mock_user_client.validate_follower_relationship.call_count == 1

    # Verify sharer details WERE fetched (for recipients, who always see identity)
    sharer_fetch_calls = [
        call
        for call in mock_user_client.get_user.call_args_list
        if call[0][0] == str(share_recipe_request.sharer_id)
    ]
    assert len(sharer_fetch_calls) == 1


@pytest.mark.django_db
@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.media_management_service_client")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.User.objects")
def test_send_notifications_without_sharer_id_anonymous(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_media_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user_dto,
):
    """Test notification without sharer_id is anonymous."""
    mock_require_current_user.return_value = mock_admin_user

    request = ShareRecipeRequest(
        recipient_ids=[uuid4()],
        recipe_id=123,
        sharer_id=None,
        share_message="Check this out!",
    )

    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_media_client.get_recipe_media_ids.return_value = []
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    response = recipe_notification_service.share_recipe_with_users(
        request=request,
    )

    assert response.queued_count == 2

    # Verify follower validation was NOT called (no sharer_id)
    mock_user_client.validate_follower_relationship.assert_not_called()

    # Verify notification_data includes is_anonymous=True
    call_args = mock_notification_service.create_notification.call_args
    notification_data = call_args[1]["notification_data"]
    assert notification_data["is_anonymous"] is True


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.media_management_service_client")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
def test_send_notifications_recipe_not_found(
    mock_recipe_client,
    mock_media_client,
    mock_require_current_user,
    mock_regular_user,
    share_recipe_request,
):
    """Test recipe not found raises RecipeNotFoundError."""
    mock_require_current_user.return_value = mock_regular_user
    mock_recipe_client.get_recipe.side_effect = RecipeNotFoundError(
        recipe_id=int(share_recipe_request.recipe_id)
    )

    with pytest.raises(RecipeNotFoundError):
        recipe_notification_service.share_recipe_with_users(
            request=share_recipe_request,
        )


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.media_management_service_client")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
def test_send_notifications_sharer_not_found(
    mock_user_client,
    mock_recipe_client,
    mock_media_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    share_recipe_request,
):
    """Test sharer not found raises UserNotFoundError."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_media_client.get_recipe_media_ids.return_value = []
    mock_user_client.get_user.side_effect = UserNotFoundError(
        user_id=str(share_recipe_request.sharer_id)
    )

    with pytest.raises(UserNotFoundError):
        recipe_notification_service.share_recipe_with_users(
            request=share_recipe_request,
        )


@pytest.mark.django_db
@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.media_management_service_client")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.User.objects")
def test_send_notifications_includes_notification_data(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_media_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user_dto,
    share_recipe_request,
):
    """Test notifications include correct notification_data."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_media_client.get_recipe_media_ids.return_value = []
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    recipe_notification_service.share_recipe_with_users(
        request=share_recipe_request,
    )

    # Verify notification_data includes expected fields
    call_args = mock_notification_service.create_notification.call_args
    notification_data = call_args[1]["notification_data"]

    assert notification_data["recipe_id"] == str(share_recipe_request.recipe_id)
    assert "template_version" in notification_data
    assert "is_anonymous" in notification_data


@pytest.mark.django_db
@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.media_management_service_client")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.User.objects")
def test_send_notifications_multiple_recipients(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_media_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user_dto,
):
    """Test handling multiple recipients correctly."""
    mock_require_current_user.return_value = mock_admin_user

    request = ShareRecipeRequest(
        recipient_ids=[uuid4(), uuid4(), uuid4()],
        recipe_id=123,
        sharer_id=uuid4(),
        share_message="Amazing recipe!",
    )

    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_media_client.get_recipe_media_ids.return_value = []
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    response = recipe_notification_service.share_recipe_with_users(
        request=request,
    )

    # 3 recipients + 1 author
    assert response.queued_count == 4
    assert len(response.notifications) == 4
    assert mock_notification_service.create_notification.call_count == 4


@pytest.mark.django_db
@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.media_management_service_client")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.User.objects")
def test_send_notifications_uses_correct_category(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_media_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user_dto,
    share_recipe_request,
):
    """Test notification uses correct category."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_media_client.get_recipe_media_ids.return_value = []
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    recipe_notification_service.share_recipe_with_users(
        request=share_recipe_request,
    )

    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["notification_category"] == "RECIPE_SHARED"
