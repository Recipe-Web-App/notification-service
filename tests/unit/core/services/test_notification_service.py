"""Tests for NotificationService."""

from unittest.mock import Mock, patch

import pytest

from core.models.notification import Notification
from core.models.user import User
from core.services.notification_service import NotificationService


@pytest.mark.django_db
class TestNotificationService:
    """Test suite for NotificationService."""

    @pytest.fixture
    def notification_service(self):
        """Create NotificationService instance."""
        with patch("core.services.notification_service.django_rq.get_queue"):
            return NotificationService()

    @pytest.fixture
    def user(self):
        """Create test user."""
        return User.objects.create(
            username="testuser",
            email="test@example.com",
            password_hash="hashed",
        )

    def test_create_notification_success(self, notification_service):
        """Test creating a notification."""
        with patch.object(notification_service, "queue_notification"):
            notification = notification_service.create_notification(
                recipient_email="test@example.com",
                subject="Test Subject",
                message="Test message",
            )

            assert notification.recipient_email == "test@example.com"
            assert notification.subject == "Test Subject"
            assert notification.message == "Test message"
            assert notification.status == Notification.PENDING

    def test_create_notification_with_user(self, notification_service, user):
        """Test creating notification with user."""
        with patch.object(notification_service, "queue_notification"):
            notification = notification_service.create_notification(
                recipient_email=user.email,
                subject="Test",
                message="Message",
                recipient=user,
            )

            assert notification.recipient == user
            assert notification.recipient_email == user.email

    def test_create_notification_with_metadata(self, notification_service):
        """Test creating notification with metadata."""
        metadata = {"event": "test_event", "user_id": "123"}

        with patch.object(notification_service, "queue_notification"):
            notification = notification_service.create_notification(
                recipient_email="test@example.com",
                subject="Test",
                message="Message",
                metadata=metadata,
            )

            assert notification.metadata == metadata

    def test_create_notification_auto_queue_true(self, notification_service):
        """Test notification is auto-queued by default."""
        with patch.object(notification_service, "queue_notification") as mock_queue:
            notification = notification_service.create_notification(
                recipient_email="test@example.com",
                subject="Test",
                message="Message",
            )

            mock_queue.assert_called_once_with(notification.notification_id)

    def test_create_notification_auto_queue_false(self, notification_service):
        """Test notification is not queued when auto_queue=False."""
        with patch.object(notification_service, "queue_notification") as mock_queue:
            notification_service.create_notification(
                recipient_email="test@example.com",
                subject="Test",
                message="Message",
                auto_queue=False,
            )

            mock_queue.assert_not_called()

    def test_queue_notification_success(self, notification_service):
        """Test queuing a notification."""
        notification = Notification.objects.create(
            recipient_email="test@example.com",
            subject="Test",
            message="Message",
        )

        notification_service.queue.enqueue = Mock()
        notification_service.queue_notification(notification.notification_id)

        assert notification_service.queue.enqueue.called
        notification.refresh_from_db()
        assert notification.status == Notification.QUEUED

    def test_queue_notification_already_sent(self, notification_service):
        """Test queuing already sent notification is skipped."""
        notification = Notification.objects.create(
            recipient_email="test@example.com",
            subject="Test",
            message="Message",
            status=Notification.SENT,
        )

        notification_service.queue.enqueue = Mock()
        notification_service.queue_notification(notification.notification_id)

        notification_service.queue.enqueue.assert_not_called()

    def test_get_notification(self, notification_service):
        """Test getting notification by ID."""
        notification = Notification.objects.create(
            recipient_email="test@example.com",
            subject="Test",
            message="Message",
        )

        result = notification_service.get_notification(notification.notification_id)

        assert result.notification_id == notification.notification_id

    def test_get_user_notifications(self, notification_service, user):
        """Test getting notifications for a user."""
        Notification.objects.create(
            recipient=user,
            recipient_email=user.email,
            subject="Test 1",
            message="Message 1",
        )
        Notification.objects.create(
            recipient=user,
            recipient_email=user.email,
            subject="Test 2",
            message="Message 2",
        )

        notifications = notification_service.get_user_notifications(user)

        assert notifications.count() == 2

    def test_get_user_notifications_filtered_by_status(
        self, notification_service, user
    ):
        """Test getting user notifications filtered by status."""
        Notification.objects.create(
            recipient=user,
            recipient_email=user.email,
            subject="Test",
            message="Message",
            status=Notification.SENT,
        )
        Notification.objects.create(
            recipient=user,
            recipient_email=user.email,
            subject="Test 2",
            message="Message 2",
            status=Notification.PENDING,
        )

        notifications = notification_service.get_user_notifications(
            user, status=Notification.SENT
        )

        assert notifications.count() == 1
        assert notifications.first().status == Notification.SENT

    def test_retry_failed_notifications(self, notification_service):
        """Test retrying failed notifications."""
        failed_notification = Notification.objects.create(
            recipient_email="test@example.com",
            subject="Test",
            message="Message",
            status=Notification.FAILED,
            retry_count=1,
        )

        notification_service.queue.enqueue = Mock()
        count = notification_service.retry_failed_notifications()

        assert count == 1
        failed_notification.refresh_from_db()
        assert failed_notification.status == Notification.QUEUED

    def test_get_notification_stats(self, notification_service):
        """Test getting notification statistics."""
        Notification.objects.create(
            recipient_email="test1@example.com",
            subject="Test 1",
            message="Message 1",
            status=Notification.PENDING,
        )
        Notification.objects.create(
            recipient_email="test2@example.com",
            subject="Test 2",
            message="Message 2",
            status=Notification.SENT,
        )

        stats = notification_service.get_notification_stats()

        assert stats["total"] == 2
        assert stats["pending"] == 1
        assert stats["sent"] == 1
