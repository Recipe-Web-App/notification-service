"""Mock helpers for component tests."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4


def create_mock_notification(**kwargs):
    """Create a mock Notification object with new two-table schema.

    Args:
        **kwargs: Override default attributes

    Returns:
        MagicMock: Mock notification object
    """
    notification_id = kwargs.pop("notification_id", uuid4())
    user_id = kwargs.pop("user_id", uuid4())

    defaults = {
        "notification_id": notification_id,
        "user_id": user_id,
        "notification_category": "RECIPE_LIKED",
        "is_read": False,
        "is_deleted": False,
        "notification_data": {
            "template_version": "1.0",
            "actor_name": "TestUser",
            "recipe_title": "Test Recipe",
        },
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    defaults.update(kwargs)

    mock = MagicMock()
    for key, value in defaults.items():
        setattr(mock, key, value)

    # Add pk attribute for Django compatibility
    mock.pk = notification_id

    return mock


def create_mock_notification_status(**kwargs):
    """Create a mock NotificationStatus object for delivery tracking.

    Args:
        **kwargs: Override default attributes

    Returns:
        MagicMock: Mock notification status object
    """
    defaults = {
        "id": kwargs.pop("id", 1),
        "notification_id": kwargs.pop("notification_id", uuid4()),
        "notification_type": "EMAIL",
        "status": "PENDING",
        "retry_count": None,
        "error_message": None,
        "recipient_email": "user@example.com",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "queued_at": None,
        "sent_at": None,
        "failed_at": None,
    }
    defaults.update(kwargs)

    mock = MagicMock()
    for key, value in defaults.items():
        setattr(mock, key, value)

    # Add helper methods
    mock.mark_queued = MagicMock()
    mock.mark_sent = MagicMock()
    mock.mark_failed = MagicMock()
    mock.increment_retry = MagicMock()
    mock.can_retry = MagicMock(return_value=True)

    return mock


def create_mock_notification_with_statuses(**kwargs):
    """Create a mock Notification with associated NotificationStatus records.

    Args:
        **kwargs: Override default attributes for notification.
            Special kwargs:
            - email_status: Status for EMAIL channel (default: "PENDING")
            - inapp_status: Status for IN_APP channel (default: "SENT")
            - include_email: Include EMAIL status (default: True)
            - include_inapp: Include IN_APP status (default: True)

    Returns:
        Tuple of (MagicMock notification, list[MagicMock statuses])
    """
    email_status = kwargs.pop("email_status", "PENDING")
    inapp_status = kwargs.pop("inapp_status", "SENT")
    include_email = kwargs.pop("include_email", True)
    include_inapp = kwargs.pop("include_inapp", True)
    recipient_email = kwargs.pop("recipient_email", "user@example.com")

    notification = create_mock_notification(**kwargs)
    statuses = []

    if include_email:
        email_stat = create_mock_notification_status(
            notification_id=notification.notification_id,
            notification_type="EMAIL",
            status=email_status,
            recipient_email=recipient_email,
        )
        statuses.append(email_stat)

    if include_inapp:
        inapp_stat = create_mock_notification_status(
            notification_id=notification.notification_id,
            notification_type="IN_APP",
            status=inapp_status,
        )
        statuses.append(inapp_stat)

    # Add statuses as related manager
    notification.statuses = MagicMock()
    notification.statuses.all = MagicMock(return_value=statuses)
    notification.statuses.filter = MagicMock(
        return_value=MagicMock(
            first=MagicMock(return_value=statuses[0] if statuses else None)
        )
    )

    return notification, statuses


def mock_auth_service_response(valid=True, user_id=123):
    """Create mock auth service response.

    Args:
        valid: Whether token is valid
        user_id: User ID to return

    Returns:
        dict: Mock response data
    """
    if valid:
        return {"json": {"user_id": user_id, "valid": True}, "status": 200}
    else:
        return {"json": {"valid": False, "error": "Invalid token"}, "status": 401}


def mock_email_service_response(success=True):
    """Create mock email service response.

    Args:
        success: Whether email send succeeded

    Returns:
        dict: Mock response data
    """
    if success:
        return {"json": {"message_id": "msg_123", "status": "sent"}, "status": 200}
    else:
        return {"json": {"error": "Failed to send"}, "status": 500}
