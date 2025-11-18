"""Unit tests for email changed notification service."""

from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from rest_framework.exceptions import PermissionDenied

from core.auth.oauth2 import OAuth2User
from core.exceptions import UserNotFoundError
from core.schemas.notification import EmailChangedRequest
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
def email_changed_request():
    """Create an email changed request."""
    return EmailChangedRequest(
        recipient_ids=[uuid4()],
        old_email="old.email@example.com",
        new_email="new.email@example.com",
    )


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
@patch("core.services.system_notification_service.notification_service")
def test_send_email_changed_notifications_sends_to_both_emails(
    mock_notification_service,
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    mock_user,
    email_changed_request,
):
    """Test email changed notifications are sent to both old and new emails."""
    # Setup
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.return_value = mock_user

    mock_notification_old = Mock()
    mock_notification_old.notification_id = uuid4()
    mock_notification_new = Mock()
    mock_notification_new.notification_id = uuid4()

    # Return different notification objects for old and new emails
    mock_notification_service.create_notification.side_effect = [
        mock_notification_old,
        mock_notification_new,
    ]

    # Execute
    result = system_notification_service.send_email_changed_notifications(
        email_changed_request
    )

    # Assert
    assert result.queued_count == 2
    assert len(result.notifications) == 2
    assert mock_notification_service.create_notification.call_count == 2


@patch("core.services.system_notification_service.require_current_user")
def test_send_email_changed_notifications_raises_permission_denied_for_non_service(
    mock_require_current_user,
    mock_non_service_user,
    email_changed_request,
):
    """Test PermissionDenied is raised for non-service callers."""
    # Setup
    mock_require_current_user.return_value = mock_non_service_user

    # Execute & Assert
    with pytest.raises(PermissionDenied) as exc_info:
        system_notification_service.send_email_changed_notifications(
            email_changed_request
        )

    assert "service-to-service authentication" in str(exc_info.value.detail)


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
def test_send_email_changed_notifications_raises_error_for_nonexistent_user(
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    email_changed_request,
):
    """Test UserNotFoundError is raised for nonexistent user."""
    # Setup
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.side_effect = UserNotFoundError(
        user_id=str(email_changed_request.recipient_ids[0])
    )

    # Execute & Assert
    with pytest.raises(UserNotFoundError):
        system_notification_service.send_email_changed_notifications(
            email_changed_request
        )


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
@patch("core.services.system_notification_service.notification_service")
def test_send_email_changed_notifications_includes_emails_in_metadata(
    mock_notification_service,
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    mock_user,
    email_changed_request,
):
    """Test notification metadata includes old and new emails."""
    # Setup
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    system_notification_service.send_email_changed_notifications(email_changed_request)

    # Assert - check both calls
    assert mock_notification_service.create_notification.call_count == 2

    # Check first call (old email)
    call_kwargs_old = mock_notification_service.create_notification.call_args_list[0][1]
    metadata_old = call_kwargs_old["metadata"]
    assert metadata_old["template_type"] == "email_changed"
    assert metadata_old["old_email"] == "old.email@example.com"
    assert metadata_old["new_email"] == "new.email@example.com"
    assert metadata_old["sent_to"] == "old_email"

    # Check second call (new email)
    call_kwargs_new = mock_notification_service.create_notification.call_args_list[1][1]
    metadata_new = call_kwargs_new["metadata"]
    assert metadata_new["template_type"] == "email_changed"
    assert metadata_new["old_email"] == "old.email@example.com"
    assert metadata_new["new_email"] == "new.email@example.com"
    assert metadata_new["sent_to"] == "new_email"


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
@patch("core.services.system_notification_service.notification_service")
@patch("core.services.system_notification_service.render_to_string")
def test_send_email_changed_notifications_renders_template_with_correct_context(
    mock_render,
    mock_notification_service,
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    mock_user,
    email_changed_request,
):
    """Test email template is rendered with correct context for both emails."""
    # Setup
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    mock_render.return_value = "<html>email content</html>"

    # Execute
    system_notification_service.send_email_changed_notifications(email_changed_request)

    # Assert - template rendered twice
    assert mock_render.call_count == 2

    # Check first call (old email - is_old_email=True)
    call_args_old = mock_render.call_args_list[0]
    assert call_args_old[0][0] == "emails/email_changed.html"
    context_old = call_args_old[0][1]
    assert context_old["is_old_email"] is True
    assert context_old["old_email"] == "old.email@example.com"
    assert context_old["new_email"] == "new.email@example.com"

    # Check second call (new email - is_old_email=False)
    call_args_new = mock_render.call_args_list[1]
    assert call_args_new[0][0] == "emails/email_changed.html"
    context_new = call_args_new[0][1]
    assert context_new["is_old_email"] is False
    assert context_new["old_email"] == "old.email@example.com"
    assert context_new["new_email"] == "new.email@example.com"


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
@patch("core.services.system_notification_service.notification_service")
def test_send_email_changed_notifications_auto_queue_enabled(
    mock_notification_service,
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    mock_user,
    email_changed_request,
):
    """Test notifications are queued for async processing."""
    # Setup
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    system_notification_service.send_email_changed_notifications(email_changed_request)

    # Assert - both calls have auto_queue=True
    assert mock_notification_service.create_notification.call_count == 2

    for call_args in mock_notification_service.create_notification.call_args_list:
        call_kwargs = call_args[1]
        assert call_kwargs["auto_queue"] is True


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
@patch("core.services.system_notification_service.notification_service")
def test_send_email_changed_notifications_uses_explicit_email_addresses(
    mock_notification_service,
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    mock_user,
    email_changed_request,
):
    """Test notifications use explicit email addresses from request."""
    # Setup
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    system_notification_service.send_email_changed_notifications(email_changed_request)

    # Assert - check recipient_email for both calls
    call_kwargs_old = mock_notification_service.create_notification.call_args_list[0][1]
    assert call_kwargs_old["recipient_email"] == "old.email@example.com"

    call_kwargs_new = mock_notification_service.create_notification.call_args_list[1][1]
    assert call_kwargs_new["recipient_email"] == "new.email@example.com"


@patch("core.services.system_notification_service.require_current_user")
@patch("core.services.system_notification_service.user_client")
@patch("core.services.system_notification_service.notification_service")
def test_send_email_changed_notifications_different_subjects(
    mock_notification_service,
    mock_user_client,
    mock_require_current_user,
    mock_service_user,
    mock_user,
    email_changed_request,
):
    """Test old and new email notifications have different subjects."""
    # Setup
    mock_require_current_user.return_value = mock_service_user
    mock_user_client.get_user.return_value = mock_user

    mock_notification = Mock()
    mock_notification.notification_id = uuid4()
    mock_notification_service.create_notification.return_value = mock_notification

    # Execute
    system_notification_service.send_email_changed_notifications(email_changed_request)

    # Assert - check subjects are different
    call_kwargs_old = mock_notification_service.create_notification.call_args_list[0][1]
    subject_old = call_kwargs_old["subject"]
    assert "Security Alert" in subject_old

    call_kwargs_new = mock_notification_service.create_notification.call_args_list[1][1]
    subject_new = call_kwargs_new["subject"]
    assert "Successfully Changed" in subject_new

    # They should be different
    assert subject_old != subject_new
