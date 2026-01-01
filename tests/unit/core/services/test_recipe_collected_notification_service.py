"""Tests for SocialNotificationService recipe-collected with two-table schema."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

from django.db.models.signals import post_save

import pytest

from core.auth.oauth2 import OAuth2User
from core.exceptions import (
    CollectionNotFoundError,
    RecipeNotFoundError,
    UserNotFoundError,
)
from core.models.user import User
from core.schemas.notification import RecipeCollectedRequest
from core.schemas.recipe import CollectionDto, RecipeDto
from core.schemas.user import UserSearchResult
from core.services.social_notification_service import (
    social_notification_service,
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
def mock_collection():
    """Create a mock collection."""
    return CollectionDto(
        collection_id=456,
        user_id=uuid4(),
        name="Test Collection",
        description="A test collection",
        created_at=datetime.now(UTC),
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
def recipe_collected_request():
    """Create a recipe collected request."""
    return RecipeCollectedRequest(
        recipient_ids=[uuid4(), uuid4()],
        recipe_id=123,
        collection_id=456,
        collector_id=uuid4(),
    )


@pytest.mark.django_db
@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.user_client")
@patch("core.services.social_notification_service.notification_service")
@patch("core.services.social_notification_service.User.objects")
def test_send_notifications_admin_scope_reveals_collector(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_collection,
    mock_user_dto,
    recipe_collected_request,
):
    """Test admin scope always reveals collector identity."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_recipe_client.get_collection.return_value = mock_collection
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    response = social_notification_service.send_recipe_collected_notifications(
        request=recipe_collected_request,
    )

    assert response.queued_count == 2
    assert len(response.notifications) == 2
    assert response.message == "Notifications queued successfully"

    # Verify recipe and collection were fetched
    mock_recipe_client.get_recipe.assert_called_once_with(
        int(recipe_collected_request.recipe_id)
    )
    mock_recipe_client.get_collection.assert_called_once_with(
        int(recipe_collected_request.collection_id)
    )

    # Verify follower validation was NOT called (admin bypass)
    mock_user_client.validate_follower_relationship.assert_not_called()

    # Verify notification service called for each recipient
    assert mock_notification_service.create_notification.call_count == 2


@pytest.mark.django_db
@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.user_client")
@patch("core.services.social_notification_service.notification_service")
@patch("core.services.social_notification_service.User.objects")
def test_send_notifications_user_scope_follower_reveals_collector(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_regular_user,
    mock_recipe,
    mock_collection,
    mock_user_dto,
    recipe_collected_request,
):
    """Test user scope with follower reveals collector identity."""
    mock_require_current_user.return_value = mock_regular_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_recipe_client.get_collection.return_value = mock_collection
    mock_user_client.get_user.return_value = mock_user_dto
    mock_user_client.validate_follower_relationship.return_value = True

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    response = social_notification_service.send_recipe_collected_notifications(
        request=recipe_collected_request,
    )

    assert response.queued_count == 2
    assert len(response.notifications) == 2

    # Verify follower validation was called
    assert mock_user_client.validate_follower_relationship.call_count == 1


@pytest.mark.django_db
@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.user_client")
@patch("core.services.social_notification_service.notification_service")
@patch("core.services.social_notification_service.User.objects")
def test_send_notifications_user_scope_non_follower_anonymous(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_regular_user,
    mock_recipe,
    mock_collection,
    mock_user_dto,
    recipe_collected_request,
):
    """Test user scope with non-follower sends anonymous notification."""
    mock_require_current_user.return_value = mock_regular_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_recipe_client.get_collection.return_value = mock_collection
    mock_user_client.get_user.return_value = mock_user_dto
    mock_user_client.validate_follower_relationship.return_value = False

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    response = social_notification_service.send_recipe_collected_notifications(
        request=recipe_collected_request,
    )

    assert response.queued_count == 2
    assert len(response.notifications) == 2

    # Verify follower validation was called
    assert mock_user_client.validate_follower_relationship.call_count == 1


@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.recipe_management_service_client")
def test_send_notifications_recipe_not_found(
    mock_recipe_client,
    mock_require_current_user,
    mock_regular_user,
    recipe_collected_request,
):
    """Test recipe not found raises RecipeNotFoundError."""
    mock_require_current_user.return_value = mock_regular_user
    mock_recipe_client.get_recipe.side_effect = RecipeNotFoundError(
        recipe_id=int(recipe_collected_request.recipe_id)
    )

    with pytest.raises(RecipeNotFoundError):
        social_notification_service.send_recipe_collected_notifications(
            request=recipe_collected_request,
        )


@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.recipe_management_service_client")
def test_send_notifications_collection_not_found(
    mock_recipe_client,
    mock_require_current_user,
    mock_regular_user,
    mock_recipe,
    recipe_collected_request,
):
    """Test collection not found raises CollectionNotFoundError."""
    mock_require_current_user.return_value = mock_regular_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_recipe_client.get_collection.side_effect = CollectionNotFoundError(
        collection_id=int(recipe_collected_request.collection_id)
    )

    with pytest.raises(CollectionNotFoundError):
        social_notification_service.send_recipe_collected_notifications(
            request=recipe_collected_request,
        )


@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.user_client")
def test_send_notifications_collector_not_found(
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_collection,
    recipe_collected_request,
):
    """Test collector not found raises UserNotFoundError."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_recipe_client.get_collection.return_value = mock_collection
    mock_user_client.get_user.side_effect = UserNotFoundError(
        user_id=str(recipe_collected_request.collector_id)
    )

    with pytest.raises(UserNotFoundError):
        social_notification_service.send_recipe_collected_notifications(
            request=recipe_collected_request,
        )


@pytest.mark.django_db
@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.user_client")
@patch("core.services.social_notification_service.notification_service")
@patch("core.services.social_notification_service.User.objects")
def test_send_notifications_includes_notification_data(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_collection,
    mock_user_dto,
    recipe_collected_request,
):
    """Test notifications include correct notification_data."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_recipe_client.get_collection.return_value = mock_collection
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    social_notification_service.send_recipe_collected_notifications(
        request=recipe_collected_request,
    )

    call_args = mock_notification_service.create_notification.call_args
    notification_data = call_args[1]["notification_data"]

    assert notification_data["recipe_id"] == str(recipe_collected_request.recipe_id)
    assert notification_data["collection_id"] == str(
        recipe_collected_request.collection_id
    )
    assert "template_version" in notification_data
    assert "is_anonymous" in notification_data


@pytest.mark.django_db
@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.user_client")
@patch("core.services.social_notification_service.notification_service")
@patch("core.services.social_notification_service.User.objects")
def test_send_notifications_multiple_recipients(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_collection,
    mock_user_dto,
):
    """Test handling multiple recipients correctly."""
    mock_require_current_user.return_value = mock_admin_user

    request = RecipeCollectedRequest(
        recipient_ids=[uuid4(), uuid4(), uuid4()],
        recipe_id=123,
        collection_id=456,
        collector_id=uuid4(),
    )

    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_recipe_client.get_collection.return_value = mock_collection
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    response = social_notification_service.send_recipe_collected_notifications(
        request=request,
    )

    assert response.queued_count == 3
    assert len(response.notifications) == 3
    assert mock_notification_service.create_notification.call_count == 3


@pytest.mark.django_db
@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.user_client")
@patch("core.services.social_notification_service.notification_service")
@patch("core.services.social_notification_service.User.objects")
def test_send_notifications_uses_correct_category(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_collection,
    mock_user_dto,
    recipe_collected_request,
):
    """Test notification uses correct category."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_recipe_client.get_collection.return_value = mock_collection
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    social_notification_service.send_recipe_collected_notifications(
        request=recipe_collected_request,
    )

    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["notification_category"] == "RECIPE_COLLECTED"
