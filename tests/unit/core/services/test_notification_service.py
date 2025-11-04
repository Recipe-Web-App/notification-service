"""Tests for NotificationService."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied

import pytest

from core.auth.oauth2 import OAuth2User
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

    def test_get_my_notifications_success(self, notification_service, user):
        """Test getting notifications for authenticated user."""
        # Create notifications for the user
        Notification.objects.create(
            recipient_email=user.email,
            subject="Test 1",
            message="Message 1",
            status=Notification.SENT,
        )
        Notification.objects.create(
            recipient_email=user.email,
            subject="Test 2",
            message="Message 2",
            status=Notification.PENDING,
        )

        mock_user = OAuth2User(
            user_id=str(user.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )

        with patch("core.auth.context.require_current_user", return_value=mock_user):
            queryset = notification_service.get_my_notifications()

            # Should return all notifications for the user
            assert queryset.count() == 2

    def test_get_my_notifications_with_status_filter(self, notification_service, user):
        """Test getting notifications filtered by status."""
        # Create notifications with different statuses
        Notification.objects.create(
            recipient_email=user.email,
            subject="Sent Notification",
            message="Message",
            status=Notification.SENT,
        )
        Notification.objects.create(
            recipient_email=user.email,
            subject="Pending Notification",
            message="Message",
            status=Notification.PENDING,
        )

        mock_user = OAuth2User(
            user_id=str(user.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )

        with patch("core.auth.context.require_current_user", return_value=mock_user):
            queryset = notification_service.get_my_notifications(
                status=Notification.SENT
            )

            # Should return only sent notifications
            assert queryset.count() == 1
            assert queryset.first().status == Notification.SENT

    def test_get_my_notifications_with_type_filter(self, notification_service, user):
        """Test getting notifications filtered by type."""
        # Create notifications
        Notification.objects.create(
            recipient_email=user.email,
            subject="Email Notification",
            message="Message",
            notification_type=Notification.EMAIL,
        )

        mock_user = OAuth2User(
            user_id=str(user.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )

        with patch("core.auth.context.require_current_user", return_value=mock_user):
            queryset = notification_service.get_my_notifications(
                notification_type=Notification.EMAIL
            )

            # Should return email notifications
            assert queryset.count() == 1
            assert queryset.first().notification_type == Notification.EMAIL

    def test_get_my_notifications_requires_scope(self, notification_service, user):
        """Test get_my_notifications requires proper scope."""
        # Mock user without required scope
        mock_user = OAuth2User(
            user_id=str(user.user_id),
            client_id="test-client",
            scopes=["some:other:scope"],
        )

        with patch(
            "core.auth.context.require_current_user", return_value=mock_user
        ) and pytest.raises(PermissionDenied):
            notification_service.get_my_notifications()

    def test_get_my_notifications_user_not_found(self, notification_service):
        """Test get_my_notifications when user not found in local DB."""
        # Mock user that doesn't exist in DB
        mock_user = OAuth2User(
            user_id=str(uuid4()),
            client_id="test-client",
            scopes=["notification:user"],
        )

        with patch("core.auth.context.require_current_user", return_value=mock_user):
            queryset = notification_service.get_my_notifications()

            # Should return empty queryset
            assert queryset.count() == 0

    def test_get_my_notifications_ordering(self, notification_service, user):
        """Test notifications are ordered by created_at DESC."""
        # Create notifications with different timestamps
        old_notif = Notification.objects.create(
            recipient_email=user.email,
            subject="Old Notification",
            message="Message",
        )
        old_notif.created_at = datetime.now(UTC) - timedelta(days=2)
        old_notif.save()

        mock_user = OAuth2User(
            user_id=str(user.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )

        with patch("core.auth.context.require_current_user", return_value=mock_user):
            queryset = notification_service.get_my_notifications()

            # Should be ordered newest first
            notifications_list = list(queryset)
            assert notifications_list[0].subject == "New Notification"
            assert notifications_list[1].subject == "Old Notification"
