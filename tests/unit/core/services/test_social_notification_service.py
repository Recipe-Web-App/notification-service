"""Tests for SocialNotificationService with two-table schema."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

from django.db.models.signals import post_save

import pytest
from rest_framework.exceptions import PermissionDenied

from core.auth.oauth2 import OAuth2User
from core.exceptions import (
    CommentNotFoundError,
    RecipeNotFoundError,
    UserNotFoundError,
)
from core.models.user import User
from core.schemas.notification import MentionRequest, NewFollowerRequest
from core.schemas.recipe import CommentDto, RecipeDto
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
def mock_follower_dto():
    """Create a mock follower DTO."""
    return UserSearchResult(
        user_id=uuid4(),
        username="newfollower",
        email="follower@example.com",
        full_name="New Follower",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_recipient_dto():
    """Create a mock recipient DTO."""
    return UserSearchResult(
        user_id=uuid4(),
        username="recipient",
        email="recipient@example.com",
        full_name="Recipient User",
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def new_follower_request():
    """Create a new follower request."""
    return NewFollowerRequest(
        follower_id=uuid4(),
        recipient_ids=[uuid4()],
    )


# =============================================================================
# New Follower Notification Tests
# =============================================================================


@pytest.mark.django_db
@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.user_client")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.notification_service")
@patch("core.services.social_notification_service.User.objects")
def test_new_follower_admin_scope_success(
    mock_user_objects,
    mock_notification_service,
    mock_recipe_client,
    mock_user_client,
    mock_require_current_user,
    mock_admin_user,
    mock_follower_dto,
    mock_recipient_dto,
    new_follower_request,
):
    """Test sending new follower notifications with admin scope succeeds."""
    mock_require_current_user.return_value = mock_admin_user
    mock_user_client.get_user.side_effect = [mock_follower_dto, mock_recipient_dto]
    mock_user_client.validate_follower_relationship.return_value = True
    mock_recipe_client.get_user_recipe_count.return_value = 5

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    response = social_notification_service.send_new_follower_notifications(
        request=new_follower_request,
    )

    assert response.queued_count == 1
    assert len(response.notifications) == 1
    assert response.message == "Notifications queued successfully"

    assert mock_user_client.get_user.call_count == 2
    mock_user_client.validate_follower_relationship.assert_called_once()
    mock_recipe_client.get_user_recipe_count.assert_called_once()
    mock_notification_service.create_notification.assert_called_once()


@patch("core.services.social_notification_service.require_current_user")
def test_new_follower_without_admin_scope_raises_permission_denied(
    mock_require_current_user,
    mock_regular_user,
    new_follower_request,
):
    """Test sending notifications without admin scope raises PermissionDenied."""
    mock_require_current_user.return_value = mock_regular_user

    with pytest.raises(PermissionDenied) as exc_info:
        social_notification_service.send_new_follower_notifications(
            request=new_follower_request,
        )

    assert "notification:admin" in str(exc_info.value.detail)


@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.user_client")
def test_new_follower_follower_not_found(
    mock_user_client,
    mock_require_current_user,
    mock_admin_user,
    new_follower_request,
):
    """Test follower not found raises UserNotFoundError."""
    mock_require_current_user.return_value = mock_admin_user
    mock_user_client.get_user.side_effect = UserNotFoundError(
        user_id=str(new_follower_request.follower_id)
    )

    with pytest.raises(UserNotFoundError):
        social_notification_service.send_new_follower_notifications(
            request=new_follower_request,
        )


@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.user_client")
@patch("core.services.social_notification_service.recipe_management_service_client")
def test_new_follower_recipient_not_found(
    mock_recipe_client,
    mock_user_client,
    mock_require_current_user,
    mock_admin_user,
    mock_follower_dto,
    new_follower_request,
):
    """Test recipient not found raises UserNotFoundError."""
    mock_require_current_user.return_value = mock_admin_user
    mock_user_client.get_user.side_effect = [
        mock_follower_dto,
        UserNotFoundError(user_id=str(new_follower_request.recipient_ids[0])),
    ]
    mock_user_client.validate_follower_relationship.return_value = True
    mock_recipe_client.get_user_recipe_count.return_value = 5

    with pytest.raises(UserNotFoundError):
        social_notification_service.send_new_follower_notifications(
            request=new_follower_request,
        )


@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.user_client")
def test_new_follower_invalid_relationship_raises_permission_denied(
    mock_user_client,
    mock_require_current_user,
    mock_admin_user,
    mock_follower_dto,
    new_follower_request,
):
    """Test invalid follower relationship raises PermissionDenied."""
    mock_require_current_user.return_value = mock_admin_user
    mock_user_client.get_user.return_value = mock_follower_dto
    mock_user_client.validate_follower_relationship.return_value = False

    with pytest.raises(PermissionDenied) as exc_info:
        social_notification_service.send_new_follower_notifications(
            request=new_follower_request,
        )

    assert "does not exist" in str(exc_info.value.detail)


@pytest.mark.django_db
@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.user_client")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.notification_service")
@patch("core.services.social_notification_service.User.objects")
def test_new_follower_includes_notification_data(
    mock_user_objects,
    mock_notification_service,
    mock_recipe_client,
    mock_user_client,
    mock_require_current_user,
    mock_admin_user,
    mock_follower_dto,
    mock_recipient_dto,
    new_follower_request,
):
    """Test notification includes correct notification_data."""
    mock_require_current_user.return_value = mock_admin_user
    mock_user_client.get_user.side_effect = [mock_follower_dto, mock_recipient_dto]
    mock_user_client.validate_follower_relationship.return_value = True
    mock_recipe_client.get_user_recipe_count.return_value = 3

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    social_notification_service.send_new_follower_notifications(
        request=new_follower_request,
    )

    call_kwargs = mock_notification_service.create_notification.call_args[1]
    notification_data = call_kwargs["notification_data"]

    assert "template_version" in notification_data
    assert "follower_id" in notification_data


@pytest.mark.django_db
@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.user_client")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.notification_service")
@patch("core.services.social_notification_service.User.objects")
def test_new_follower_uses_correct_category(
    mock_user_objects,
    mock_notification_service,
    mock_recipe_client,
    mock_user_client,
    mock_require_current_user,
    mock_admin_user,
    mock_follower_dto,
    mock_recipient_dto,
    new_follower_request,
):
    """Test notification uses correct category."""
    mock_require_current_user.return_value = mock_admin_user
    mock_user_client.get_user.side_effect = [mock_follower_dto, mock_recipient_dto]
    mock_user_client.validate_follower_relationship.return_value = True
    mock_recipe_client.get_user_recipe_count.return_value = 0

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    social_notification_service.send_new_follower_notifications(
        request=new_follower_request,
    )

    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["notification_category"] == "NEW_FOLLOWER"


@pytest.mark.django_db
@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.user_client")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.notification_service")
@patch("core.services.social_notification_service.User.objects")
def test_new_follower_multiple_recipients(
    mock_user_objects,
    mock_notification_service,
    mock_recipe_client,
    mock_user_client,
    mock_require_current_user,
    mock_admin_user,
    mock_follower_dto,
    mock_recipient_dto,
):
    """Test sending notifications to multiple recipients."""
    mock_require_current_user.return_value = mock_admin_user
    request = NewFollowerRequest(
        follower_id=uuid4(),
        recipient_ids=[uuid4(), uuid4()],
    )

    mock_user_client.get_user.side_effect = [
        mock_follower_dto,
        mock_recipient_dto,
        mock_recipient_dto,
    ]
    mock_user_client.validate_follower_relationship.return_value = True
    mock_recipe_client.get_user_recipe_count.return_value = 5

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    response = social_notification_service.send_new_follower_notifications(
        request=request,
    )

    assert response.queued_count == 2
    assert len(response.notifications) == 2
    assert mock_user_client.validate_follower_relationship.call_count == 2
    assert mock_notification_service.create_notification.call_count == 2


# =============================================================================
# Mention Notification Tests
# =============================================================================


@pytest.fixture
def mock_comment():
    """Create a mock comment."""
    return CommentDto(
        comment_id=456,
        recipe_id=123,
        user_id=uuid4(),
        comment_text="This is a great recipe! Thanks @user for the tip!",
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_recipe():
    """Create a mock recipe."""
    return RecipeDto(
        recipe_id=123,
        user_id=uuid4(),
        title="Amazing Chocolate Cake",
        servings=Decimal("8"),
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def mention_request():
    """Create a mention request."""
    return MentionRequest(
        comment_id=456,
        recipient_ids=[uuid4()],
    )


@pytest.mark.django_db
@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.user_client")
@patch("core.services.social_notification_service.notification_service")
@patch("core.services.social_notification_service.User.objects")
def test_mention_admin_scope_success(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_comment,
    mock_recipe,
    mock_follower_dto,
    mock_recipient_dto,
    mention_request,
):
    """Test sending mention notifications with admin scope succeeds."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_comment.return_value = mock_comment
    mock_user_client.get_user.side_effect = [mock_follower_dto, mock_recipient_dto]
    mock_recipe_client.get_recipe.return_value = mock_recipe

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    response = social_notification_service.send_mention_notifications(
        request=mention_request,
    )

    assert response.queued_count == 1
    assert len(response.notifications) == 1
    assert response.message == "Notifications queued successfully"

    mock_recipe_client.get_comment.assert_called_once_with(mention_request.comment_id)
    assert mock_user_client.get_user.call_count == 2
    mock_recipe_client.get_recipe.assert_called_once()
    mock_notification_service.create_notification.assert_called_once()


@patch("core.services.social_notification_service.require_current_user")
def test_mention_without_admin_scope_raises_permission_denied(
    mock_require_current_user,
    mock_regular_user,
    mention_request,
):
    """Test mention notifications without admin scope raise PermissionDenied."""
    mock_require_current_user.return_value = mock_regular_user

    with pytest.raises(PermissionDenied) as exc_info:
        social_notification_service.send_mention_notifications(
            request=mention_request,
        )

    assert "notification:admin" in str(exc_info.value.detail)


@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.recipe_management_service_client")
def test_mention_comment_not_found(
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mention_request,
):
    """Test comment not found raises CommentNotFoundError."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_comment.side_effect = CommentNotFoundError(
        comment_id=str(mention_request.comment_id)
    )

    with pytest.raises(CommentNotFoundError):
        social_notification_service.send_mention_notifications(
            request=mention_request,
        )


@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.user_client")
def test_mention_commenter_not_found(
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_comment,
    mention_request,
):
    """Test commenter not found raises UserNotFoundError."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_comment.return_value = mock_comment
    mock_user_client.get_user.side_effect = UserNotFoundError(
        user_id=str(mock_comment.user_id)
    )

    with pytest.raises(UserNotFoundError):
        social_notification_service.send_mention_notifications(
            request=mention_request,
        )


@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.user_client")
def test_mention_recipe_not_found(
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_comment,
    mock_follower_dto,
    mention_request,
):
    """Test recipe not found raises RecipeNotFoundError."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_comment.return_value = mock_comment
    mock_user_client.get_user.return_value = mock_follower_dto
    mock_recipe_client.get_recipe.side_effect = RecipeNotFoundError(
        recipe_id=mock_comment.recipe_id
    )

    with pytest.raises(RecipeNotFoundError):
        social_notification_service.send_mention_notifications(
            request=mention_request,
        )


@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.user_client")
def test_mention_recipient_not_found(
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_comment,
    mock_recipe,
    mock_follower_dto,
    mention_request,
):
    """Test recipient not found raises UserNotFoundError."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_comment.return_value = mock_comment
    mock_user_client.get_user.side_effect = [
        mock_follower_dto,
        UserNotFoundError(user_id=str(mention_request.recipient_ids[0])),
    ]
    mock_recipe_client.get_recipe.return_value = mock_recipe

    with pytest.raises(UserNotFoundError):
        social_notification_service.send_mention_notifications(
            request=mention_request,
        )


@pytest.mark.django_db
@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.user_client")
@patch("core.services.social_notification_service.notification_service")
@patch("core.services.social_notification_service.User.objects")
def test_mention_includes_notification_data(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_comment,
    mock_recipe,
    mock_follower_dto,
    mock_recipient_dto,
    mention_request,
):
    """Test notification includes correct notification_data."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_comment.return_value = mock_comment
    mock_user_client.get_user.side_effect = [mock_follower_dto, mock_recipient_dto]
    mock_recipe_client.get_recipe.return_value = mock_recipe

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    social_notification_service.send_mention_notifications(
        request=mention_request,
    )

    call_kwargs = mock_notification_service.create_notification.call_args[1]
    notification_data = call_kwargs["notification_data"]

    assert "template_version" in notification_data
    assert notification_data["comment_id"] == str(mention_request.comment_id)
    assert notification_data["recipe_id"] == str(mock_comment.recipe_id)


@pytest.mark.django_db
@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.user_client")
@patch("core.services.social_notification_service.notification_service")
@patch("core.services.social_notification_service.User.objects")
def test_mention_uses_correct_category(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_comment,
    mock_recipe,
    mock_follower_dto,
    mock_recipient_dto,
    mention_request,
):
    """Test notification uses correct category."""
    mock_require_current_user.return_value = mock_admin_user
    mock_recipe_client.get_comment.return_value = mock_comment
    mock_user_client.get_user.side_effect = [mock_follower_dto, mock_recipient_dto]
    mock_recipe_client.get_recipe.return_value = mock_recipe

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    social_notification_service.send_mention_notifications(
        request=mention_request,
    )

    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["notification_category"] == "MENTION"


@pytest.mark.django_db
@patch("core.services.social_notification_service.require_current_user")
@patch("core.services.social_notification_service.recipe_management_service_client")
@patch("core.services.social_notification_service.user_client")
@patch("core.services.social_notification_service.notification_service")
@patch("core.services.social_notification_service.User.objects")
def test_mention_multiple_recipients(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_recipe_client,
    mock_require_current_user,
    mock_admin_user,
    mock_comment,
    mock_recipe,
    mock_follower_dto,
    mock_recipient_dto,
):
    """Test sending mention notifications to multiple recipients."""
    mock_require_current_user.return_value = mock_admin_user
    request = MentionRequest(
        comment_id=456,
        recipient_ids=[uuid4(), uuid4()],
    )

    mock_recipe_client.get_comment.return_value = mock_comment
    mock_user_client.get_user.side_effect = [
        mock_follower_dto,
        mock_recipient_dto,
        mock_recipient_dto,
    ]
    mock_recipe_client.get_recipe.return_value = mock_recipe

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    response = social_notification_service.send_mention_notifications(
        request=request,
    )

    assert response.queued_count == 2
    assert len(response.notifications) == 2
    assert mock_notification_service.create_notification.call_count == 2
