"""Unit tests for maintenance notification service."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from rest_framework.exceptions import PermissionDenied

from core.auth.oauth2 import OAuth2User
from core.enums import UserRole
from core.schemas.notification import MaintenanceRequest
from core.services.system_notification_service import (
    system_notification_service,
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
def mock_non_admin_user():
    """Create a mock non-admin user."""
    return OAuth2User(
        user_id=str(uuid4()),
        client_id="test-client",
        scopes=["notification:user"],
    )


@pytest.fixture
def maintenance_request():
    """Create a maintenance request."""
    now = datetime.now(UTC)
    return MaintenanceRequest(
        maintenance_start=now + timedelta(hours=1),
        maintenance_end=now + timedelta(hours=3),
        description="Scheduled database maintenance",
        admin_only=False,
    )


@pytest.fixture
def mock_users():
    """Create mock user instances."""
    user1 = Mock()
    user1.user_id = uuid4()
    user1.email = "user1@example.com"
    user1.username = "user1"
    user1.full_name = "User One"
    user1.role = UserRole.USER.value

    user2 = Mock()
    user2.user_id = uuid4()
    user2.email = "user2@example.com"
    user2.username = "user2"
    user2.full_name = None

    return [user1, user2]


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.User")
@patch("core.services.system_notification_service.notification_service")
def test_send_maintenance_notifications_broadcasts_to_all_users(
    mock_notification_service,
    mock_user_model,
    mock_require_current_user,
    mock_admin_user,
    mock_users,
    maintenance_request,
):
    """Test adminOnly=False broadcasts to all users."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_queryset = Mock()
    mock_queryset.count.return_value = 2
    mock_queryset.__iter__.return_value = iter(mock_users)
    mock_user_model.objects.filter.return_value = mock_queryset

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    result = system_notification_service.send_maintenance_notifications(
        maintenance_request
    )

    # Assert
    assert result.queued_count == 2
    assert len(result.notifications) == 2
    mock_user_model.objects.filter.assert_called_once_with(is_active=True)


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.User")
@patch("core.services.system_notification_service.notification_service")
def test_send_maintenance_notifications_sends_only_to_admins(
    mock_notification_service,
    mock_user_model,
    mock_require_current_user,
    mock_admin_user,
    mock_users,
):
    """Test adminOnly=True sends only to admins."""
    # Setup
    now = datetime.now(UTC)
    admin_only_request = MaintenanceRequest(
        maintenance_start=now + timedelta(hours=1),
        maintenance_end=now + timedelta(hours=3),
        description="Backend maintenance",
        admin_only=True,
    )

    mock_require_current_user.return_value = mock_admin_user
    mock_queryset = Mock()
    mock_queryset.count.return_value = 1
    mock_queryset.__iter__.return_value = iter([mock_users[0]])
    mock_user_model.objects.filter.return_value = mock_queryset

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    result = system_notification_service.send_maintenance_notifications(
        admin_only_request
    )

    # Assert
    assert result.queued_count == 1
    mock_user_model.objects.filter.assert_called_once_with(
        role=UserRole.ADMIN.value,
        is_active=True,
    )


@patch("core.services.system_notification_service.require_current_user")
def test_send_maintenance_notifications_raises_permission_denied_for_non_admin(
    mock_require_current_user,
    mock_non_admin_user,
    maintenance_request,
):
    """Test PermissionDenied is raised for non-admin users."""
    # Setup
    mock_require_current_user.return_value = mock_non_admin_user

    # Execute & Assert
    with pytest.raises(PermissionDenied) as exc_info:
        system_notification_service.send_maintenance_notifications(maintenance_request)

    assert "notification:admin" in str(exc_info.value.detail)


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.User")
@patch("core.services.system_notification_service.notification_service")
def test_send_maintenance_notifications_includes_correct_metadata(
    mock_notification_service,
    mock_user_model,
    mock_require_current_user,
    mock_admin_user,
    mock_users,
    maintenance_request,
):
    """Test notification metadata is correct."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_queryset = Mock()
    mock_queryset.__iter__.return_value = iter([mock_users[0]])
    mock_user_model.objects.filter.return_value = mock_queryset

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    system_notification_service.send_maintenance_notifications(maintenance_request)

    # Assert
    call_kwargs = mock_notification_service.create_notification.call_args[1]
    metadata = call_kwargs["metadata"]
    assert metadata["template_type"] == "maintenance"
    assert "recipient_id" in metadata
    assert "maintenance_start" in metadata
    assert "maintenance_end" in metadata
    assert metadata["admin_only"] is False


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.User")
@patch("core.services.system_notification_service.notification_service")
@patch("core.services.system_notification_service.render_to_string")
def test_send_maintenance_notifications_renders_template_with_correct_context(
    mock_render,
    mock_notification_service,
    mock_user_model,
    mock_require_current_user,
    mock_admin_user,
    mock_users,
    maintenance_request,
):
    """Test email template is rendered with correct context."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_queryset = Mock()
    mock_queryset.__iter__.return_value = iter([mock_users[0]])
    mock_user_model.objects.filter.return_value = mock_queryset

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    mock_render.return_value = "<html>email content</html>"

    # Execute
    system_notification_service.send_maintenance_notifications(maintenance_request)

    # Assert
    assert mock_render.call_count == 1
    call_args = mock_render.call_args[0]
    assert call_args[0] == "emails/maintenance.html"
    context = call_args[1]
    assert "recipient_name" in context
    assert "maintenance_start" in context
    assert "maintenance_end" in context
    assert "description" in context
    assert "app_url" in context


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.User")
@patch("core.services.system_notification_service.notification_service")
def test_send_maintenance_notifications_auto_queue_enabled(
    mock_notification_service,
    mock_user_model,
    mock_require_current_user,
    mock_admin_user,
    mock_users,
    maintenance_request,
):
    """Test notifications are queued for async processing."""
    # Setup
    mock_require_current_user.return_value = mock_admin_user
    mock_queryset = Mock()
    mock_queryset.__iter__.return_value = iter([mock_users[0]])
    mock_user_model.objects.filter.return_value = mock_queryset

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    system_notification_service.send_maintenance_notifications(maintenance_request)

    # Assert
    call_kwargs = mock_notification_service.create_notification.call_args[1]
    assert call_kwargs["auto_queue"] is True
