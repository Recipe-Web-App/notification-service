"""Unit tests for password changed notification service with two-table schema."""

from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import uuid4

from django.db.models.signals import post_save

import pytest
from rest_framework.exceptions import PermissionDenied

from core.auth.oauth2 import OAuth2User
from core.exceptions import UserNotFoundError
from core.models.user import User
from core.schemas.notification import PasswordChangedRequest
from core.schemas.user import UserSearchResult
from core.services.system_notification_service import (
    system_notification_service,
)
from core.signals.user_signals import send_welcome_email


@pytest.fixture(autouse=True)
def disconnect_signals():
    """Disconnect signals for all tests."""
    post_save.disconnect(send_welcome_email, sender=User)
    yield
    post_save.connect(send_welcome_email, sender=User)


@pytest.fixture
def mock_service_user():
    """Create a mock service-to-service user (user_id == client_id)."""
    user_id = str(uuid4())
    return OAuth2User(
        user_id=user_id,
        client_id=user_id,  # Service-to-service: user_id == client_id
        scopes=["notification:admin"],
    )


@pytest.fixture
def mock_non_service_user():
    """Create a mock non-service user (user_id != client_id)."""
    return OAuth2User(
        user_id=str(uuid4()),
        client_id="different-client-id",
        scopes=["notification:admin"],
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
def password_changed_request():
    """Create a password changed request."""
    return PasswordChangedRequest(
        recipient_ids=[uuid4()],
    )


@pytest.mark.django_db
@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
@patch("core.services.system_notification_service.notification_service")
@patch("core.services.system_notification_service.User.objects")
def test_send_password_changed_creates_notification(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    mock_user,
    password_changed_request,
):
    """Test password changed notification is created successfully."""
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.return_value = mock_user

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    result = system_notification_service.send_password_changed_notifications(
        password_changed_request
    )

    assert result.queued_count == 1
    assert len(result.notifications) == 1
    assert mock_notification_service.create_notification.call_count == 1


@patch("core.services.system_notification_service.require_current_user")
def test_send_password_changed_raises_permission_denied_for_non_service(
    mock_require_current_user,
    mock_non_service_user,
    password_changed_request,
):
    """Test PermissionDenied is raised for non-service callers."""
    mock_require_current_user.return_value = mock_non_service_user

    with pytest.raises(PermissionDenied) as exc_info:
        system_notification_service.send_password_changed_notifications(
            password_changed_request
        )

    assert "service-to-service authentication" in str(exc_info.value.detail)


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
def test_send_password_changed_raises_error_for_nonexistent_user(
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    password_changed_request,
):
    """Test UserNotFoundError is raised for nonexistent user."""
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.side_effect = UserNotFoundError(
        user_id=str(password_changed_request.recipient_ids[0])
    )

    with pytest.raises(UserNotFoundError):
        system_notification_service.send_password_changed_notifications(
            password_changed_request
        )


@pytest.mark.django_db
@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
@patch("core.services.system_notification_service.notification_service")
@patch("core.services.system_notification_service.User.objects")
def test_send_password_changed_includes_notification_data(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    mock_user,
    password_changed_request,
):
    """Test notification_data is correct."""
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.return_value = mock_user

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    system_notification_service.send_password_changed_notifications(
        password_changed_request
    )

    call_kwargs = mock_notification_service.create_notification.call_args[1]
    notification_data = call_kwargs["notification_data"]
    assert "template_version" in notification_data
    assert "recipient_id" in notification_data


@pytest.mark.django_db
@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
@patch("core.services.system_notification_service.notification_service")
@patch("core.services.system_notification_service.User.objects")
def test_send_password_changed_uses_correct_category(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    mock_user,
    password_changed_request,
):
    """Test notification uses correct category."""
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.return_value = mock_user

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    system_notification_service.send_password_changed_notifications(
        password_changed_request
    )

    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["notification_category"] == "PASSWORD_CHANGED"


@pytest.mark.django_db
@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
@patch("core.services.system_notification_service.notification_service")
@patch("core.services.system_notification_service.User.objects")
def test_send_password_changed_batch_processing(
    mock_user_objects,
    mock_notification_service,
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    mock_user,
):
    """Test batch processing creates one notification per recipient."""
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.return_value = mock_user

    mock_db_user = Mock()
    mock_user_objects.get.return_value = mock_db_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = (mock_notification, [])

    batch_request = PasswordChangedRequest(
        recipient_ids=[uuid4(), uuid4(), uuid4()],
    )

    result = system_notification_service.send_password_changed_notifications(
        batch_request
    )

    assert result.queued_count == 3
    assert len(result.notifications) == 3
    assert mock_notification_service.create_notification.call_count == 3
