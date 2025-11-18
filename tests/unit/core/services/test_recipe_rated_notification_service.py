"""Unit tests for recipe rated notification service."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from core.auth.oauth2 import OAuth2User
from core.exceptions import RecipeNotFoundError
from core.models import Review
from core.schemas.notification import RecipeRatedRequest
from core.schemas.recipe import RecipeDto
from core.schemas.user import UserSearchResult
from core.services.recipe_notification_service import (
    recipe_notification_service,
)


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
def mock_review():
    """Create a mock review."""
    review = Mock(spec=Review)
    review.review_id = 1
    review.recipe_id = 123
    review.user_id = uuid4()
    review.rating = Decimal("4.5")
    review.created_at = datetime.now(UTC)
    return review


@pytest.fixture
def recipe_rated_request():
    """Create a recipe rated request."""
    return RecipeRatedRequest(
        recipient_ids=[uuid4()],
        recipe_id=123,
        rater_id=uuid4(),
    )


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.models.Review.objects")
def test_send_recipe_rated_notifications_with_admin_scope_reveals_rater(
    mock_review_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user,
    mock_review,
    recipe_rated_request,
):
    """Test admin scope reveals rater identity."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_review_objects.get.return_value = mock_review
    mock_review_objects.filter.return_value.aggregate.return_value = {
        "average": Decimal("4.3")
    }
    mock_review_objects.filter.return_value.count.return_value = 5
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    result = recipe_notification_service.send_recipe_rated_notifications(
        recipe_rated_request
    )

    # Assert
    assert result.queued_count == 1
    assert len(result.notifications) == 1

    # Verify rater identity was fetched (admin reveals identity)
    assert mock_user_client.get_user.call_count >= 1

    # Verify notification metadata includes is_anonymous: False
    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["metadata"]["is_anonymous"] is False


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.models.Review.objects")
def test_send_recipe_rated_notifications_with_user_scope_and_follower_reveals_rater(
    mock_review_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_authenticated_user,
    mock_recipe,
    mock_user,
    mock_review,
    recipe_rated_request,
):
    """Test user scope with follower relationship reveals rater identity."""
    # Setup
    mock_require_current_user.return_value = mock_authenticated_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_review_objects.get.return_value = mock_review
    mock_review_objects.filter.return_value.aggregate.return_value = {
        "average": Decimal("4.3")
    }
    mock_review_objects.filter.return_value.count.return_value = 5
    mock_user_client.validate_follower_relationship.return_value = True
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    result = recipe_notification_service.send_recipe_rated_notifications(
        recipe_rated_request
    )

    # Assert
    assert result.queued_count == 1

    # Verify follower relationship was validated
    mock_user_client.validate_follower_relationship.assert_called_once()

    # Verify notification metadata shows non-anonymous
    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["metadata"]["is_anonymous"] is False


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.models.Review.objects")
def test_send_recipe_rated_notifications_with_user_scope_and_non_follower_anonymous(
    mock_review_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_authenticated_user,
    mock_recipe,
    mock_user,
    mock_review,
    recipe_rated_request,
):
    """Test user scope without follower sends anonymous notification."""
    # Setup
    mock_require_current_user.return_value = mock_authenticated_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_review_objects.get.return_value = mock_review
    mock_review_objects.filter.return_value.aggregate.return_value = {
        "average": Decimal("4.3")
    }
    mock_review_objects.filter.return_value.count.return_value = 5
    mock_user_client.validate_follower_relationship.return_value = False
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    result = recipe_notification_service.send_recipe_rated_notifications(
        recipe_rated_request
    )

    # Assert
    assert result.queued_count == 1

    # Verify notification metadata shows anonymous
    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["metadata"]["is_anonymous"] is True


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
def test_send_recipe_rated_notifications_raises_error_for_nonexistent_recipe(
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    recipe_rated_request,
):
    """Test RecipeNotFoundError is raised for nonexistent recipe."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.side_effect = RecipeNotFoundError(recipe_id=123)

    # Execute & Assert
    with pytest.raises(RecipeNotFoundError):
        recipe_notification_service.send_recipe_rated_notifications(
            recipe_rated_request
        )


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.models.Review.objects")
def test_send_recipe_rated_notifications_raises_error_for_nonexistent_review(
    mock_review_objects,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    recipe_rated_request,
):
    """Test ValueError is raised when review doesn't exist."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_review_objects.get.side_effect = Review.DoesNotExist()

    # Execute & Assert
    with pytest.raises(ValueError, match="No rating found"):
        recipe_notification_service.send_recipe_rated_notifications(
            recipe_rated_request
        )


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.models.Review.objects")
def test_send_recipe_rated_notifications_includes_rating_data_in_metadata(
    mock_review_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user,
    mock_review,
    recipe_rated_request,
):
    """Test notification metadata includes rating data."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_review_objects.get.return_value = mock_review
    mock_review_objects.filter.return_value.aggregate.return_value = {
        "average": Decimal("4.3")
    }
    mock_review_objects.filter.return_value.count.return_value = 5
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    recipe_notification_service.send_recipe_rated_notifications(recipe_rated_request)

    # Assert
    call_kwargs = mock_notification_service.create_notification.call_args[1]
    metadata = call_kwargs["metadata"]

    assert metadata["template_type"] == "recipe_rated"
    assert metadata["recipe_id"] == str(recipe_rated_request.recipe_id)
    assert metadata["rater_id"] == str(recipe_rated_request.rater_id)
    assert "rating_value" in metadata
    assert "average_rating" in metadata
    assert float(metadata["rating_value"]) == 4.5
    assert float(metadata["average_rating"]) == 4.3


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.models.Review.objects")
@patch("core.services.recipe_notification_service.render_to_string")
def test_send_recipe_rated_notifications_renders_email_template(
    mock_render,
    mock_review_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user,
    mock_review,
    recipe_rated_request,
):
    """Test email template is rendered with correct context."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_review_objects.get.return_value = mock_review
    mock_review_objects.filter.return_value.aggregate.return_value = {
        "average": Decimal("4.3")
    }
    mock_review_objects.filter.return_value.count.return_value = 5
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    mock_render.return_value = "<html>email content</html>"

    # Execute
    recipe_notification_service.send_recipe_rated_notifications(recipe_rated_request)

    # Assert
    mock_render.assert_called_once()
    call_args = mock_render.call_args[0]

    assert call_args[0] == "emails/recipe_rated.html"
    context = call_args[1]

    assert "recipe_title" in context
    assert "individual_rating" in context
    assert "average_rating" in context
    assert "total_reviews" in context
    assert context["individual_rating"] == 4.5
    assert context["average_rating"] == 4.3
    assert context["total_reviews"] == 5


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.models.Review.objects")
def test_send_recipe_rated_notifications_auto_queue_enabled(
    mock_review_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user,
    mock_review,
    recipe_rated_request,
):
    """Test notifications are queued for async processing."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_recipe.return_value = mock_recipe
    mock_review_objects.get.return_value = mock_review
    mock_review_objects.filter.return_value.aggregate.return_value = {
        "average": Decimal("4.3")
    }
    mock_review_objects.filter.return_value.count.return_value = 5
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    recipe_notification_service.send_recipe_rated_notifications(recipe_rated_request)

    # Assert
    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["auto_queue"] is True


@patch("core.services.recipe_notification_service.require_current_user")
@patch("core.services.recipe_notification_service.recipe_management_service_client")
@patch("core.services.recipe_notification_service.user_client")
@patch("core.services.recipe_notification_service.notification_service")
@patch("core.models.Review.objects")
def test_send_recipe_rated_notifications_handles_multiple_recipients(
    mock_review_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_recipe,
    mock_user,
    mock_review,
):
    """Test multiple recipients receive notifications."""
    # Setup
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
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    result = recipe_notification_service.send_recipe_rated_notifications(request)

    # Assert
    assert result.queued_count == 3
    assert len(result.notifications) == 3
    assert mock_notification_service.create_notification.call_count == 3
