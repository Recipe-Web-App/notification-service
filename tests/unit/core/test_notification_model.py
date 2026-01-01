"""Tests for Notification model with two-table schema."""

from django.db.models.signals import post_save

import pytest

from core.enums.notification import NotificationCategory
from core.models.notification import Notification
from core.models.user import User
from core.signals.user_signals import send_welcome_email


@pytest.mark.django_db
class TestNotificationModel:
    """Test suite for Notification model with new two-table schema."""

    @pytest.fixture(autouse=True)
    def disconnect_signals(self):
        """Disconnect signals for all tests."""
        post_save.disconnect(send_welcome_email, sender=User)
        yield
        post_save.connect(send_welcome_email, sender=User)

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
        """Create test notification with new schema."""
        return Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={
                "template_version": "1.0",
                "actor_name": "John",
                "recipe_title": "Test Recipe",
            },
        )

    def test_notification_creation(self, notification):
        """Test notification is created with correct defaults."""
        assert notification.notification_id is not None
        assert notification.is_read is False
        assert notification.is_deleted is False
        assert notification.created_at is not None
        assert notification.updated_at is not None

    def test_notification_category(self, notification):
        """Test notification has correct category."""
        assert (
            notification.notification_category
            == NotificationCategory.RECIPE_LIKED.value
        )

    def test_notification_data_jsonb(self, notification):
        """Test notification_data JSONB field works correctly."""
        assert notification.notification_data["template_version"] == "1.0"
        assert notification.notification_data["actor_name"] == "John"
        assert notification.notification_data["recipe_title"] == "Test Recipe"

    def test_notification_str_representation(self, notification):
        """Test notification string representation."""
        result = str(notification)
        assert NotificationCategory.RECIPE_LIKED.value in result
        assert "user" in result

    def test_notification_repr(self, notification):
        """Test notification repr."""
        result = repr(notification)
        assert "Notification" in result
        assert str(notification.notification_id) in result
        assert "category=" in result

    def test_notification_user_relationship(self, user, notification):
        """Test notification is linked to user."""
        assert notification.user == user
        assert notification.user_id == user.user_id

    def test_notification_ordering(self, user):
        """Test notifications are ordered by created_at descending."""
        notif1 = Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
        )
        notif2 = Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.NEW_FOLLOWER.value,
            notification_data={"template_version": "1.0"},
        )

        notifications = list(Notification.objects.all())
        assert notifications[0].notification_id == notif2.notification_id
        assert notifications[1].notification_id == notif1.notification_id

    def test_notification_with_all_categories(self, user):
        """Test notifications can be created with different categories."""
        categories = [
            NotificationCategory.RECIPE_LIKED.value,
            NotificationCategory.RECIPE_COMMENTED.value,
            NotificationCategory.NEW_FOLLOWER.value,
            NotificationCategory.WELCOME.value,
            NotificationCategory.PASSWORD_RESET.value,
        ]

        for category in categories:
            notification = Notification.objects.create(
                user=user,
                notification_category=category,
                notification_data={"template_version": "1.0"},
            )
            assert notification.notification_category == category

    def test_notification_is_read_toggle(self, notification):
        """Test is_read can be toggled."""
        assert notification.is_read is False

        notification.is_read = True
        notification.save()
        notification.refresh_from_db()

        assert notification.is_read is True

    def test_notification_soft_delete(self, notification):
        """Test is_deleted soft delete flag works."""
        assert notification.is_deleted is False

        notification.is_deleted = True
        notification.save()
        notification.refresh_from_db()

        assert notification.is_deleted is True
        # Notification still exists in database
        assert Notification.objects.filter(
            notification_id=notification.notification_id
        ).exists()

    def test_notification_filter_excludes_deleted(self, user):
        """Test filtering can exclude soft-deleted notifications."""
        active = Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
            is_deleted=False,
        )
        deleted = Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.NEW_FOLLOWER.value,
            notification_data={"template_version": "1.0"},
            is_deleted=True,
        )

        active_notifications = Notification.objects.filter(is_deleted=False)
        assert active.notification_id in [
            n.notification_id for n in active_notifications
        ]
        assert deleted.notification_id not in [
            n.notification_id for n in active_notifications
        ]

    def test_notification_filter_by_read_status(self, user):
        """Test filtering by is_read status."""
        unread = Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
            is_read=False,
        )
        read = Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.NEW_FOLLOWER.value,
            notification_data={"template_version": "1.0"},
            is_read=True,
        )

        unread_notifications = Notification.objects.filter(is_read=False)
        assert unread.notification_id in [
            n.notification_id for n in unread_notifications
        ]
        assert read.notification_id not in [
            n.notification_id for n in unread_notifications
        ]

    def test_notification_with_rich_notification_data(self, user):
        """Test notification with complex notification_data structure."""
        rich_data = {
            "template_version": "1.0",
            "actor_id": "user-123",
            "actor_name": "Jane Doe",
            "recipe_id": 456,
            "recipe_title": "Delicious Pasta",
            "comment_preview": "This looks amazing!",
            "nested": {
                "key": "value",
                "list": [1, 2, 3],
            },
        }

        notification = Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_COMMENTED.value,
            notification_data=rich_data,
        )

        notification.refresh_from_db()
        assert notification.notification_data == rich_data
        assert notification.notification_data["nested"]["key"] == "value"
        assert notification.notification_data["nested"]["list"] == [1, 2, 3]

    def test_notification_user_cascade_related_name(self, user):
        """Test user has related notifications accessible via related_name."""
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

        assert user.notifications.count() == 2
