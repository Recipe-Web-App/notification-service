"""Mock helpers for component tests."""

from unittest.mock import MagicMock


def create_mock_notification(**kwargs):
    """Create a mock Notification object.

    Args:
        **kwargs: Override default attributes

    Returns:
        MagicMock: Mock notification object
    """
    defaults = {
        "id": 1,
        "recipient": "user@example.com",
        "message": "Test message",
        "type": "email",
        "status": "pending",
    }
    defaults.update(kwargs)

    mock = MagicMock()
    for key, value in defaults.items():
        setattr(mock, key, value)

    return mock


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
