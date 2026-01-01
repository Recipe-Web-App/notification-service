"""Tests for NotificationService with two-table schema."""

from unittest.mock import Mock, patch
from uuid import uuid4

from django.db.models.signals import post_save
from django.utils import timezone

import pytest

from core.auth.oauth2 import OAuth2User
from core.enums.notification import (
    NotificationCategory,
    NotificationStatusEnum,
    NotificationType,
)
from core.models.notification import Notification
from core.models.notification_status import NotificationStatus
from core.models.user import User
from core.services.notification_service import NotificationService
from core.signals.user_signals import send_welcome_email


@pytest.mark.django_db
class TestNotificationService:
    """Test suite for NotificationService with two-table schema."""

    @pytest.fixture(autouse=True)
    def disconnect_signals(self):
        """Disconnect signals for all tests."""
        post_save.disconnect(send_welcome_email, sender=User)
        yield
        post_save.connect(send_welcome_email, sender=User)

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

    def test_create_notification_success(self, notification_service, user):
        """Test creating a notification with new schema."""
        with patch.object(notification_service, "queue_notification"):
            notification, statuses = notification_service.create_notification(
                user=user,
                notification_category=NotificationCategory.RECIPE_LIKED.value,
                notification_data={
                    "template_version": "1.0",
                    "actor_name": "TestActor",
                    "recipe_title": "Test Recipe",
                },
                recipient_email=user.email,
            )

            # Check notification
            assert notification.user == user
            assert (
                notification.notification_category
                == NotificationCategory.RECIPE_LIKED.value
            )
            assert notification.notification_data["template_version"] == "1.0"
            assert notification.is_read is False
            assert notification.is_deleted is False

            # Check statuses
            assert len(statuses) == 2
            email_status = next(
                s
                for s in statuses
                if s.notification_type == NotificationType.EMAIL.value
            )
            inapp_status = next(
                s
                for s in statuses
                if s.notification_type == NotificationType.IN_APP.value
            )

            assert email_status.status == NotificationStatusEnum.PENDING.value
            assert email_status.recipient_email == user.email
            assert inapp_status.status == NotificationStatusEnum.SENT.value

    def test_create_notification_auto_queue_true(self, notification_service, user):
        """Test notification is auto-queued by default."""
        with patch.object(notification_service, "queue_notification") as mock_queue:
            notification, _statuses = notification_service.create_notification(
                user=user,
                notification_category=NotificationCategory.NEW_FOLLOWER.value,
                notification_data={"template_version": "1.0"},
                recipient_email=user.email,
            )

            mock_queue.assert_called_once_with(notification.notification_id)

    def test_create_notification_auto_queue_false(self, notification_service, user):
        """Test notification is not queued when auto_queue=False."""
        with patch.object(notification_service, "queue_notification") as mock_queue:
            notification_service.create_notification(
                user=user,
                notification_category=NotificationCategory.RECIPE_LIKED.value,
                notification_data={"template_version": "1.0"},
                recipient_email=user.email,
                auto_queue=False,
            )

            mock_queue.assert_not_called()

    def test_queue_notification_success(self, notification_service, user):
        """Test queuing a notification updates EMAIL status to QUEUED."""
        notification = Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
        )
        email_status = NotificationStatus.objects.create(
            notification=notification,
            notification_type=NotificationType.EMAIL.value,
            status=NotificationStatusEnum.PENDING.value,
            recipient_email=user.email,
        )

        notification_service.queue.enqueue = Mock()
        notification_service.queue_notification(notification.notification_id)

        assert notification_service.queue.enqueue.called
        email_status.refresh_from_db()
        assert email_status.status == NotificationStatusEnum.QUEUED.value
        assert email_status.queued_at is not None

    def test_queue_notification_already_sent(self, notification_service, user):
        """Test queuing already sent notification is skipped."""
        notification = Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
        )
        NotificationStatus.objects.create(
            notification=notification,
            notification_type=NotificationType.EMAIL.value,
            status=NotificationStatusEnum.SENT.value,
            recipient_email=user.email,
            sent_at=timezone.now(),
        )

        notification_service.queue.enqueue = Mock()
        notification_service.queue_notification(notification.notification_id)

        notification_service.queue.enqueue.assert_not_called()

    def test_get_notification(self, notification_service, user):
        """Test getting notification by ID."""
        notification = Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
        )

        result = notification_service.get_notification(notification.notification_id)

        assert result.notification_id == notification.notification_id

    def test_get_user_notifications(self, notification_service, user):
        """Test getting notifications for a user."""
        Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
        )
        Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.NEW_FOLLOWER.value,
            notification_data={"template_version": "1.0"},
        )

        notifications = notification_service.get_notifications_for_user(user)

        assert notifications.count() == 2

    def test_get_user_notifications_excludes_deleted(self, notification_service, user):
        """Test getting user notifications excludes soft-deleted."""
        Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
            is_deleted=False,
        )
        Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.NEW_FOLLOWER.value,
            notification_data={"template_version": "1.0"},
            is_deleted=True,  # Soft deleted
        )

        notifications = notification_service.get_notifications_for_user(user)

        # Should only return non-deleted
        assert notifications.count() == 1

    def test_get_pending_email_statuses(self, notification_service, user):
        """Test getting pending email statuses for queuing."""
        # Create notification with PENDING email status
        notif1 = Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
        )
        NotificationStatus.objects.create(
            notification=notif1,
            notification_type=NotificationType.EMAIL.value,
            status=NotificationStatusEnum.PENDING.value,
            recipient_email=user.email,
        )

        # Create notification with SENT status (should be excluded)
        notif2 = Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.NEW_FOLLOWER.value,
            notification_data={"template_version": "1.0"},
        )
        NotificationStatus.objects.create(
            notification=notif2,
            notification_type=NotificationType.EMAIL.value,
            status=NotificationStatusEnum.SENT.value,
            recipient_email=user.email,
        )

        pending = notification_service.get_pending_email_statuses()

        assert pending.count() == 1
        assert pending.first().notification == notif1


@pytest.mark.django_db
class TestNotificationServiceAuthentication:
    """Test suite for NotificationService authentication."""

    @pytest.fixture(autouse=True)
    def disconnect_signals(self):
        """Disconnect signals for all tests."""
        post_save.disconnect(send_welcome_email, sender=User)
        yield
        post_save.connect(send_welcome_email, sender=User)

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

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_get_my_notifications_with_authenticated_user(
        self, mock_require, mock_get_current, notification_service, user
    ):
        """Test getting current user's notifications."""
        oauth_user = OAuth2User(
            user_id=str(user.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_require.return_value = oauth_user
        mock_get_current.return_value = oauth_user

        # Create notifications for user
        Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
        )
        Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.NEW_FOLLOWER.value,
            notification_data={"template_version": "1.0"},
        )

        notifications = notification_service.get_my_notifications()

        assert notifications.count() == 2

    @patch("core.auth.context.get_current_user")
    @patch("core.auth.context.require_current_user")
    def test_get_my_notifications_excludes_deleted(
        self, mock_require, mock_get_current, notification_service, user
    ):
        """Test that deleted notifications are excluded."""
        oauth_user = OAuth2User(
            user_id=str(user.user_id),
            client_id="test-client",
            scopes=["notification:user"],
        )
        mock_require.return_value = oauth_user
        mock_get_current.return_value = oauth_user

        # Create active notification
        Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
            is_deleted=False,
        )
        # Create deleted notification
        Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.NEW_FOLLOWER.value,
            notification_data={"template_version": "1.0"},
            is_deleted=True,
        )

        notifications = notification_service.get_my_notifications()

        assert notifications.count() == 1


@pytest.mark.django_db
class TestNotificationServiceRetry:
    """Test suite for NotificationService retry functionality."""

    @pytest.fixture(autouse=True)
    def disconnect_signals(self):
        """Disconnect signals for all tests."""
        post_save.disconnect(send_welcome_email, sender=User)
        yield
        post_save.connect(send_welcome_email, sender=User)

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

    def test_retry_failed_notifications(self, notification_service, user):
        """Test retrying failed notification statuses."""
        # Create failed notification
        notification = Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
        )
        NotificationStatus.objects.create(
            notification=notification,
            notification_type=NotificationType.EMAIL.value,
            status=NotificationStatusEnum.FAILED.value,
            retry_count=1,
            recipient_email=user.email,
        )

        notification_service.queue.enqueue = Mock()
        count = notification_service.retry_failed_notifications()

        assert count >= 1

    def test_retry_failed_notifications_respects_max_retries(
        self, notification_service, user
    ):
        """Test that exhausted retries are not retried."""
        # Create exhausted notification
        notification = Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
        )
        NotificationStatus.objects.create(
            notification=notification,
            notification_type=NotificationType.EMAIL.value,
            status=NotificationStatusEnum.FAILED.value,
            retry_count=3,  # At max retries
            recipient_email=user.email,
        )

        notification_service.queue.enqueue = Mock()
        count = notification_service.retry_failed_notifications()

        # Exhausted notification should not be retried
        assert count == 0


@pytest.mark.django_db
class TestNotificationServiceEdgeCases:
    """Test suite for NotificationService edge cases."""

    @pytest.fixture(autouse=True)
    def disconnect_signals(self):
        """Disconnect signals for all tests."""
        post_save.disconnect(send_welcome_email, sender=User)
        yield
        post_save.connect(send_welcome_email, sender=User)

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

    def test_get_notification_not_found(self, notification_service):
        """Test getting non-existent notification raises error."""
        from core.models.notification import Notification

        with pytest.raises(Notification.DoesNotExist):
            notification_service.get_notification(uuid4())

    def test_create_notification_with_all_categories(self, notification_service, user):
        """Test creating notifications with different categories."""
        categories = [
            NotificationCategory.RECIPE_LIKED.value,
            NotificationCategory.RECIPE_COMMENTED.value,
            NotificationCategory.NEW_FOLLOWER.value,
            NotificationCategory.WELCOME.value,
            NotificationCategory.PASSWORD_RESET.value,
        ]

        for category in categories:
            with patch.object(notification_service, "queue_notification"):
                notification, statuses = notification_service.create_notification(
                    user=user,
                    notification_category=category,
                    notification_data={"template_version": "1.0"},
                    recipient_email=user.email,
                )

                assert notification.notification_category == category
                assert len(statuses) == 2

    def test_create_notification_with_rich_notification_data(
        self, notification_service, user
    ):
        """Test creating notification with complex notification_data."""
        notification_data = {
            "template_version": "1.0",
            "actor_id": str(uuid4()),
            "actor_name": "John Doe",
            "recipe_id": 12345,
            "recipe_title": "Delicious Pasta",
            "comment_id": 67890,
            "comment_preview": "This looks amazing!",
        }

        with patch.object(notification_service, "queue_notification"):
            notification, _ = notification_service.create_notification(
                user=user,
                notification_category=NotificationCategory.RECIPE_COMMENTED.value,
                notification_data=notification_data,
                recipient_email=user.email,
            )

            assert notification.notification_data == notification_data
            assert notification.notification_data["recipe_title"] == "Delicious Pasta"
