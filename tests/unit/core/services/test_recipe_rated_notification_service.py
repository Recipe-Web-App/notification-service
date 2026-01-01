"""Unit tests for recipe rated notification service with two-table schema."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

from django.db.models.signals import post_save

import pytest

from core.auth.oauth2 import OAuth2User
from core.exceptions import RecipeNotFoundError
from core.models import Review
from core.models.user import User
from core.schemas.notification import RecipeRatedRequest
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
def mock_authenticated_user():
    """Create a mock authenticated user."""
    return OAuth2User(
        user_id=str(uuid4()),
        client_id="test-client",
        scopes=["notification:user"],
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
def mock_review():
    """Create a mock review."""
    review = Mock(spec=Review)
    review.review_id = 1
    review.recipe_id = 123
    review.user_id = uuid4()
    review.rating = Decimal("4.5")
    review.created_at = datetime.now(UTC)
    return review


@pytest.mark.django_db
@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.User.objects")
@patch("core.models.Review.objects")
def test_send_recipe_rated_notifications_with_admin_scope_reveals_rater(
    mock_review_objects,
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user_dto,
    mock_review,
):
    """Test admin scope reveals rater identity."""
    recipient_id = uuid4()
    request = RecipeRatedRequest(
        recipient_ids=[recipient_id],
        recipe_id=123,
        rater_id=uuid4(),
    )

    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_review_objects.get.return_value = mock_review
    mock_review_objects.filter.return_value.aggregate.return_value = {
        "average": Decimal("4.3")
    }
    mock_review_objects.filter.return_value.count.return_value = 5
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_db_user.user_id = recipient_id
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    result = recipe_notification_service.send_recipe_rated_notifications(request)

    assert result.queued_count == 1
    assert len(result.notifications) == 1
    assert mock_user_client.get_user.call_count >= 1

    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["notification_data"]["is_anonymous"] is False


@pytest.mark.django_db
@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.User.objects")
@patch("core.models.Review.objects")
def test_send_recipe_rated_notifications_with_follower_reveals_rater(
    mock_review_objects,
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_authenticated_user,
    mock_recipe,
    mock_user_dto,
    mock_review,
):
    """Test user scope with follower relationship reveals rater identity."""
    recipient_id = uuid4()
    request = RecipeRatedRequest(
        recipient_ids=[recipient_id],
        recipe_id=123,
        rater_id=uuid4(),
    )

    mock_require_current_user.return_value = mock_authenticated_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_review_objects.get.return_value = mock_review
    mock_review_objects.filter.return_value.aggregate.return_value = {
        "average": Decimal("4.3")
    }
    mock_review_objects.filter.return_value.count.return_value = 5
    mock_user_client.validate_follower_relationship.return_value = True
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_db_user.user_id = recipient_id
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    result = recipe_notification_service.send_recipe_rated_notifications(request)

    assert result.queued_count == 1
    mock_user_client.validate_follower_relationship.assert_called_once()

    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["notification_data"]["is_anonymous"] is False


@pytest.mark.django_db
@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.User.objects")
@patch("core.models.Review.objects")
def test_send_recipe_rated_notifications_non_follower_anonymous(
    mock_review_objects,
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_authenticated_user,
    mock_recipe,
    mock_user_dto,
    mock_review,
):
    """Test user scope without follower sends anonymous notification."""
    recipient_id = uuid4()
    request = RecipeRatedRequest(
        recipient_ids=[recipient_id],
        recipe_id=123,
        rater_id=uuid4(),
    )

    mock_require_current_user.return_value = mock_authenticated_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_review_objects.get.return_value = mock_review
    mock_review_objects.filter.return_value.aggregate.return_value = {
        "average": Decimal("4.3")
    }
    mock_review_objects.filter.return_value.count.return_value = 5
    mock_user_client.validate_follower_relationship.return_value = False
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_db_user.user_id = recipient_id
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    result = recipe_notification_service.send_recipe_rated_notifications(request)

    assert result.queued_count == 1

    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["notification_data"]["is_anonymous"] is True


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
def test_send_recipe_rated_notifications_raises_error_for_nonexistent_recipe(
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
):
    """Test RecipeNotFoundError is raised for nonexistent recipe."""
    request = RecipeRatedRequest(
        recipient_ids=[uuid4()],
        recipe_id=123,
        rater_id=uuid4(),
    )

    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.side_effect = RecipeNotFoundError(recipe_id=123)

    with pytest.raises(RecipeNotFoundError):
        recipe_notification_service.send_recipe_rated_notifications(request)


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.models.Review.objects")
def test_send_recipe_rated_notifications_raises_error_for_nonexistent_review(
    mock_review_objects,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
):
    """Test ValueError is raised when review doesn't exist."""
    request = RecipeRatedRequest(
        recipient_ids=[uuid4()],
        recipe_id=123,
        rater_id=uuid4(),
    )

    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_review_objects.get.side_effect = Review.DoesNotExist()

    with pytest.raises(ValueError, match="No rating found"):
        recipe_notification_service.send_recipe_rated_notifications(request)


@pytest.mark.django_db
@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.User.objects")
@patch("core.models.Review.objects")
def test_send_recipe_rated_notifications_includes_rating_data(
    mock_review_objects,
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user_dto,
    mock_review,
):
    """Test notification_data includes rating data."""
    recipient_id = uuid4()
    rater_id = uuid4()
    request = RecipeRatedRequest(
        recipient_ids=[recipient_id],
        recipe_id=123,
        rater_id=rater_id,
    )

    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_review_objects.get.return_value = mock_review
    mock_review_objects.filter.return_value.aggregate.return_value = {
        "average": Decimal("4.3")
    }
    mock_review_objects.filter.return_value.count.return_value = 5
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_db_user.user_id = recipient_id
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    recipe_notification_service.send_recipe_rated_notifications(request)

    call_kwargs = mock_notification_service.create_notification.call_args[1]
    notification_data = call_kwargs["notification_data"]

    assert notification_data["recipe_id"] == "123"
    assert notification_data["rater_id"] == str(rater_id)
    assert "individual_rating" in notification_data
    assert "average_rating" in notification_data
    assert notification_data["template_version"] == "1.0"


@pytest.mark.django_db
@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.User.objects")
@patch("core.models.Review.objects")
def test_send_recipe_rated_notifications_uses_correct_category(
    mock_review_objects,
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user_dto,
    mock_review,
):
    """Test notification uses correct category."""
    recipient_id = uuid4()
    request = RecipeRatedRequest(
        recipient_ids=[recipient_id],
        recipe_id=123,
        rater_id=uuid4(),
    )

    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_review_objects.get.return_value = mock_review
    mock_review_objects.filter.return_value.aggregate.return_value = {
        "average": Decimal("4.3")
    }
    mock_review_objects.filter.return_value.count.return_value = 5
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_db_user.user_id = recipient_id
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    recipe_notification_service.send_recipe_rated_notifications(request)

    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["notification_category"] == "RECIPE_RATED"


@pytest.mark.django_db
@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.services.recipe_notification_service.User.objects")
@patch("core.models.Review.objects")
def test_send_recipe_rated_notifications_handles_multiple_recipients(
    mock_review_objects,
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user_dto,
    mock_review,
):
    """Test multiple recipients receive notifications."""
    request = RecipeRatedRequest(
        recipient_ids=[uuid4(), uuid4(), uuid4()],
        recipe_id=123,
        rater_id=uuid4(),
    )

    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_review_objects.get.return_value = mock_review
    mock_review_objects.filter.return_value.aggregate.return_value = {
        "average": Decimal("4.3")
    }
    mock_review_objects.filter.return_value.count.return_value = 5
    mock_user_client.get_user.return_value = mock_user_dto

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    result = recipe_notification_service.send_recipe_rated_notifications(request)

    assert result.queued_count == 3
    assert len(result.notifications) == 3
    assert mock_notification_service.create_notification.call_count == 3
