"""Tests for user signal handlers with two-table schema."""

from unittest.mock import patch

import pytest

from core.models.user import User


@pytest.mark.django_db
class TestUserSignals:
    """Test suite for user signal handlers."""

    def test_send_welcome_email_on_user_creation(self):
        """Test welcome notification is created when user is created."""
        with patch("core.signals.user_signals.notification_service") as mock_service:
            user = User.objects.create(
                username="newuser",
                email="newuser@example.com",
                password_hash="hashed",
            )

            mock_service.create_notification.assert_called_once()
            call_args = mock_service.create_notification.call_args
            assert call_args.kwargs["user"] == user
            assert call_args.kwargs["notification_category"] == "WELCOME"
            assert call_args.kwargs["recipient_email"] == "newuser@example.com"

    def test_welcome_email_not_sent_on_update(self):
        """Test welcome notification is not created when user is updated."""
        # First create user with signal active - need to mock the initial creation
        with patch("core.signals.user_signals.notification_service"):
            user = User.objects.create(
                username="testuser",
                email="test@example.com",
                password_hash="hashed",
            )

        # Now test that updating user doesn't trigger signal
        with patch("core.signals.user_signals.notification_service") as mock_service:
            user.email = "newemail@example.com"
            user.save()

            mock_service.create_notification.assert_not_called()

    def test_welcome_email_includes_username_in_notification_data(self):
        """Test welcome notification includes username in notification_data."""
        with patch("core.signals.user_signals.notification_service") as mock_service:
            User.objects.create(
                username="johndoe",
                email="john@example.com",
                password_hash="hashed",
            )

            call_args = mock_service.create_notification.call_args
            notification_data = call_args.kwargs["notification_data"]
            assert notification_data["username"] == "johndoe"
            assert notification_data["template_version"] == "1.0"

    def test_welcome_email_handles_exception(self):
        """Test user creation succeeds even if notification fails."""
        with patch("core.signals.user_signals.notification_service") as mock_service:
            mock_service.create_notification.side_effect = Exception("Email error")

            user = User.objects.create(
                username="testuser",
                email="test@example.com",
                password_hash="hashed",
            )

            # User should still be created
            assert user.user_id is not None

    def test_welcome_notification_uses_correct_category(self):
        """Test welcome notification uses WELCOME category."""
        with patch("core.signals.user_signals.notification_service") as mock_service:
            User.objects.create(
                username="testuser",
                email="test@example.com",
                password_hash="hashed",
            )

            call_args = mock_service.create_notification.call_args
            assert call_args.kwargs["notification_category"] == "WELCOME"

    def test_welcome_notification_passes_user_instance(self):
        """Test welcome notification receives user instance."""
        with patch("core.signals.user_signals.notification_service") as mock_service:
            user = User.objects.create(
                username="testuser",
                email="test@example.com",
                password_hash="hashed",
            )

            call_args = mock_service.create_notification.call_args
            passed_user = call_args.kwargs["user"]
            assert passed_user.user_id == user.user_id
            assert passed_user.username == "testuser"
