"""Unit tests for password changed notification service."""

from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from rest_framework.exceptions import PermissionDenied

from core.auth.oauth2 import OAuth2User
from core.exceptions import UserNotFoundError
from core.schemas.notification import PasswordChangedRequest
from core.schemas.user import UserSearchResult
from core.services.system_notification_service import (
    system_notification_service,
)


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


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
@patch("core.services.system_notification_service.notification_service")
def test_send_password_changed_notifications_creates_notification(
    mock_notification_service,
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    mock_user,
    password_changed_request,
):
    """Test password changed notification is created successfully."""
    # Setup
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    result = system_notification_service.send_password_changed_notifications(
        password_changed_request
    )

    # Assert
    assert result.queued_count == 1
    assert len(result.notifications) == 1
    assert mock_notification_service.create_notification.call_count == 1


@patch("core.services.system_notification_service.require_current_user")
def test_send_password_changed_notifications_raises_permission_denied_for_non_service(
    mock_require_current_user,
    mock_non_service_user,
    password_changed_request,
):
    """Test PermissionDenied is raised for non-service callers."""
    # Setup
    mock_require_current_user.return_value = mock_non_service_user

    # Execute & Assert
    with pytest.raises(PermissionDenied) as exc_info:
        system_notification_service.send_password_changed_notifications(
            password_changed_request
        )

    assert "service-to-service authentication" in str(exc_info.value.detail)


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
def test_send_password_changed_notifications_raises_error_for_nonexistent_user(
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    password_changed_request,
):
    """Test UserNotFoundError is raised for nonexistent user."""
    # Setup
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.side_effect = UserNotFoundError(
        user_id=str(password_changed_request.recipient_ids[0])
    )

    # Execute & Assert
    with pytest.raises(UserNotFoundError):
        system_notification_service.send_password_changed_notifications(
            password_changed_request
        )


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
@patch("core.services.system_notification_service.notification_service")
def test_send_password_changed_notifications_includes_correct_metadata(
    mock_notification_service,
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    mock_user,
    password_changed_request,
):
    """Test notification metadata is correct."""
    # Setup
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    system_notification_service.send_password_changed_notifications(
        password_changed_request
    )

    # Assert
    call_kwargs = mock_notification_service.create_notification.call_args[1]
    metadata = call_kwargs["metadata"]
    assert metadata["template_type"] == "password_changed"
    assert "recipient_id" in metadata


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
@patch("core.services.system_notification_service.notification_service")
@patch("core.services.system_notification_service.render_to_string")
def test_send_password_changed_notifications_renders_template_with_correct_context(
    mock_render,
    mock_notification_service,
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    mock_user,
    password_changed_request,
):
    """Test email template is rendered with correct context."""
    # Setup
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    mock_render.return_value = "<html>email content</html>"

    # Execute
    system_notification_service.send_password_changed_notifications(
        password_changed_request
    )

    # Assert - template rendered once
    assert mock_render.call_count == 1

    # Check template and context
    call_args = mock_render.call_args[0]
    assert call_args[0] == "emails/password_changed.html"
    context = call_args[1]
    assert "recipient_name" in context
    assert "app_url" in context


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
@patch("core.services.system_notification_service.notification_service")
def test_send_password_changed_notifications_auto_queue_enabled(
    mock_notification_service,
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    mock_user,
    password_changed_request,
):
    """Test notifications are queued for async processing."""
    # Setup
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    system_notification_service.send_password_changed_notifications(
        password_changed_request
    )

    # Assert - auto_queue=True
    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["auto_queue"] is True


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
@patch("core.services.system_notification_service.notification_service")
def test_send_password_changed_notifications_uses_user_email(
    mock_notification_service,
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    mock_user,
    password_changed_request,
):
    """Test notification uses user's current email address."""
    # Setup
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    system_notification_service.send_password_changed_notifications(
        password_changed_request
    )

    # Assert - uses user's email
    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["recipient_email"] == mock_user.email


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
@patch("core.services.system_notification_service.notification_service")
def test_send_password_changed_notifications_batch_processing(
    mock_notification_service,
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    mock_user,
):
    """Test batch processing creates one notification per recipient."""
    # Setup
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Create request with 3 recipients
    batch_request = PasswordChangedRequest(
        recipient_ids=[uuid4(), uuid4(), uuid4()],
    )

    # Execute
    result = system_notification_service.send_password_changed_notifications(
        batch_request
    )

    # Assert - 3 notifications created
    assert result.queued_count == 3
    assert len(result.notifications) == 3
    assert mock_notification_service.create_notification.call_count == 3
