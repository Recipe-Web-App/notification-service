"""Tests for user signal handlers."""

from unittest.mock import patch

import pytest

from core.models.user import User


@pytest.mark.django_db
class TestUserSignals:
    """Test suite for user signal handlers."""

    def test_send_welcome_email_on_user_creation(self):
        """Test welcome email is sent when user is created."""
        with patch("core.signals.user_signals.notification_service") as mock_service:
            User.objects.create(
                username="newuser",
                email="newuser@example.com",
                password_hash="hashed",
            )

            mock_service.create_notification.assert_called_once()
            call_args = mock_service.create_notification.call_args
            assert call_args[1]["recipient_email"] == "newuser@example.com"
            assert "Welcome" in call_args[1]["subject"]

    def test_welcome_email_not_sent_on_update(self):
        """Test welcome email is not sent when user is updated."""
        user = User.objects.create(
            username="testuser",
            email="test@example.com",
            password_hash="hashed",
        )

        with patch("core.signals.user_signals.notification_service") as mock_service:
            user.email = "newemail@example.com"
            user.save()

            mock_service.create_notification.assert_not_called()

    def test_welcome_email_includes_username(self):
        """Test welcome email includes user's username."""
        with patch("core.signals.user_signals.notification_service") as mock_service:
            User.objects.create(
                username="johndoe",
                email="john@example.com",
                password_hash="hashed",
            )

            call_args = mock_service.create_notification.call_args
            assert "johndoe" in call_args[1]["subject"]

    def test_welcome_email_handles_exception(self):
        """Test user creation succeeds even if email fails."""
        with patch("core.signals.user_signals.notification_service") as mock_service:
            mock_service.create_notification.side_effect = Exception("Email error")

            user = User.objects.create(
                username="testuser",
                email="test@example.com",
                password_hash="hashed",
            )

            assert user.user_id is not None

    def test_welcome_email_includes_metadata(self):
        """Test welcome email includes user metadata."""
        with patch("core.signals.user_signals.notification_service") as mock_service:
            user = User.objects.create(
                username="testuser",
                email="test@example.com",
                password_hash="hashed",
            )

            call_args = mock_service.create_notification.call_args
            metadata = call_args[1]["metadata"]
            assert metadata["event"] == "user_created"
            assert metadata["user_id"] == str(user.user_id)
            assert metadata["username"] == "testuser"
