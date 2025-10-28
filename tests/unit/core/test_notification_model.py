"""Tests for Notification model."""

import pytest

from core.models.notification import Notification
from core.models.user import User


@pytest.mark.django_db
class TestNotificationModel:
    """Test suite for Notification model."""

    @pytest.fixture
    def user(self):
        """Create test user."""
        return User.objects.create(
            username="testuser",
            email="test@example.com",
            password_hash="hashed",
        )

    @pytest.fixture
    def notification(self, user):
        """Create test notification."""
        return Notification.objects.create(
            recipient=user,
            recipient_email=user.email,
            subject="Test Subject",
            message="Test message",
        )

    def test_notification_creation(self, notification):
        """Test notification is created with correct defaults."""
        assert notification.notification_id is not None
        assert notification.status == Notification.PENDING
        assert notification.retry_count == 0
        assert notification.max_retries == 3
        assert notification.notification_type == Notification.EMAIL

    def test_notification_str_representation(self, notification):
        """Test notification string representation."""
        result = str(notification)
        assert "email" in result
        assert notification.recipient_email in result
        assert notification.status in result

    def test_notification_repr(self, notification):
        """Test notification repr."""
        result = repr(notification)
        assert "Notification" in result
        assert str(notification.notification_id) in result

    def test_mark_queued(self, notification):
        """Test marking notification as queued."""
        notification.mark_queued()

        assert notification.status == Notification.QUEUED
        assert notification.queued_at is not None

    def test_mark_sent(self, notification):
        """Test marking notification as sent."""
        notification.mark_sent()

        assert notification.status == Notification.SENT
        assert notification.sent_at is not None

    def test_mark_failed(self, notification):
        """Test marking notification as failed."""
        error_msg = "SMTP connection failed"
        notification.mark_failed(error_msg)

        assert notification.status == Notification.FAILED
        assert notification.failed_at is not None
        assert notification.error_message == error_msg

    def test_increment_retry(self, notification):
        """Test incrementing retry count."""
        initial_count = notification.retry_count
        notification.increment_retry()

        assert notification.retry_count == initial_count + 1

    def test_can_retry_true(self, notification):
        """Test can_retry returns True when retries available."""
        notification.retry_count = 1
        notification.status = Notification.FAILED

        assert notification.can_retry() is True

    def test_can_retry_false_max_retries(self, notification):
        """Test can_retry returns False when max retries reached."""
        notification.retry_count = 3
        notification.status = Notification.FAILED

        assert notification.can_retry() is False

    def test_can_retry_false_already_sent(self, notification):
        """Test can_retry returns False when already sent."""
        notification.retry_count = 1
        notification.status = Notification.SENT

        assert notification.can_retry() is False

    def test_notification_with_metadata(self):
        """Test notification with metadata."""
        metadata = {"template": "welcome", "user_id": "123"}
        notification = Notification.objects.create(
            recipient_email="test@example.com",
            subject="Test",
            message="Message",
            metadata=metadata,
        )

        assert notification.metadata == metadata

    def test_notification_without_user(self):
        """Test notification can be created without user."""
        notification = Notification.objects.create(
            recipient_email="test@example.com",
            subject="Test",
            message="Message",
        )

        assert notification.recipient is None
        assert notification.recipient_email == "test@example.com"

    def test_notification_ordering(self):
        """Test notifications are ordered by created_at descending."""
        notif1 = Notification.objects.create(
            recipient_email="test1@example.com",
            subject="First",
            message="Message 1",
        )
        notif2 = Notification.objects.create(
            recipient_email="test2@example.com",
            subject="Second",
            message="Message 2",
        )

        notifications = list(Notification.objects.all())
        assert notifications[0].notification_id == notif2.notification_id
        assert notifications[1].notification_id == notif1.notification_id

    def test_notification_type_choices(self):
        """Test different notification types can be created."""
        email_notif = Notification.objects.create(
            recipient_email="test@example.com",
            subject="Email Test",
            message="Message",
            notification_type=Notification.EMAIL,
        )
        assert email_notif.notification_type == Notification.EMAIL

        in_app_notif = Notification.objects.create(
            recipient_email="test@example.com",
            subject="In-App Test",
            message="Message",
            notification_type=Notification.IN_APP,
        )
        assert in_app_notif.notification_type == Notification.IN_APP
