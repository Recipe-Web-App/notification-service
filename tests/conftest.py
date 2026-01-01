"""Pytest configuration and shared fixtures."""

import os
from uuid import uuid4

import django
from django.db.models.signals import post_save
from django.test import Client
from django.utils import timezone

import pytest

# Configure Django settings for tests
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "notification_service.settings_test")
django.setup()

from core.enums.notification import (
    NotificationCategory,
    NotificationStatusEnum,
    NotificationType,
)
from core.models import Notification, NotificationStatus, User
from core.signals.user_signals import send_welcome_email


@pytest.fixture
def api_client():
    """Provide Django test client."""
    return Client()


@pytest.fixture
def authenticated_client():
    """Provide authenticated test client."""
    client = Client()
    # Add authentication logic here
    return client


@pytest.fixture
def disconnect_signals():
    """Disconnect user signals to avoid side effects during tests."""
    post_save.disconnect(send_welcome_email, sender=User)
    yield
    post_save.connect(send_welcome_email, sender=User)


@pytest.fixture
def test_user(disconnect_signals):
    """Create a test user with signals disconnected."""
    user = User.objects.create(
        username=f"testuser_{uuid4().hex[:8]}",
        email=f"test_{uuid4().hex[:8]}@example.com",
        password_hash="hashed_password",
    )
    yield user
    user.delete()


@pytest.fixture
def notification_factory(test_user):
    """Factory to create Notification with associated NotificationStatus records.

    Returns a callable that creates notifications with the new two-table schema.
    """
    created_notifications = []

    def _create_notification(
        user=None,
        notification_category=NotificationCategory.RECIPE_LIKED.value,
        notification_data=None,
        is_read=False,
        is_deleted=False,
        include_email_status=True,
        include_inapp_status=True,
        email_status=NotificationStatusEnum.PENDING.value,
        inapp_status=NotificationStatusEnum.SENT.value,
        recipient_email=None,
    ):
        """Create a notification with status records.

        Args:
            user: User instance (defaults to test_user).
            notification_category: Category for the notification.
            notification_data: JSONB data (defaults to sample data).
            is_read: Whether notification is read.
            is_deleted: Whether notification is soft deleted.
            include_email_status: Create EMAIL status record.
            include_inapp_status: Create IN_APP status record.
            email_status: Status for EMAIL channel.
            inapp_status: Status for IN_APP channel.
            recipient_email: Email for EMAIL status (defaults to user.email).

        Returns:
            Tuple of (Notification, list[NotificationStatus]).
        """
        target_user = user or test_user
        data = notification_data or {
            "template_version": "1.0",
            "actor_name": "TestUser",
            "recipe_title": "Test Recipe",
        }

        notification = Notification.objects.create(
            user=target_user,
            notification_category=notification_category,
            notification_data=data,
            is_read=is_read,
            is_deleted=is_deleted,
        )
        created_notifications.append(notification)

        statuses = []

        if include_email_status:
            email_stat = NotificationStatus.objects.create(
                notification=notification,
                notification_type=NotificationType.EMAIL.value,
                status=email_status,
                recipient_email=recipient_email or target_user.email,
            )
            if email_status == NotificationStatusEnum.SENT.value:
                email_stat.sent_at = timezone.now()
                email_stat.save(update_fields=["sent_at"])
            elif email_status == NotificationStatusEnum.QUEUED.value:
                email_stat.queued_at = timezone.now()
                email_stat.save(update_fields=["queued_at"])
            elif email_status == NotificationStatusEnum.FAILED.value:
                email_stat.failed_at = timezone.now()
                email_stat.error_message = "Test failure"
                email_stat.save(update_fields=["failed_at", "error_message"])
            statuses.append(email_stat)

        if include_inapp_status:
            inapp_stat = NotificationStatus.objects.create(
                notification=notification,
                notification_type=NotificationType.IN_APP.value,
                status=inapp_status,
            )
            if inapp_status == NotificationStatusEnum.SENT.value:
                inapp_stat.sent_at = timezone.now()
                inapp_stat.save(update_fields=["sent_at"])
            statuses.append(inapp_stat)

        return notification, statuses

    yield _create_notification

    # Cleanup - delete all created notifications
    for notif in created_notifications:
        NotificationStatus.objects.filter(notification=notif).delete()
        notif.delete()


@pytest.fixture
def notification_status_factory():
    """Factory to create NotificationStatus records for existing notifications."""
    created_statuses = []

    def _create_status(
        notification,
        notification_type=NotificationType.EMAIL.value,
        status=NotificationStatusEnum.PENDING.value,
        retry_count=None,
        error_message=None,
        recipient_email=None,
    ):
        """Create a notification status record.

        Args:
            notification: Parent Notification instance.
            notification_type: Delivery channel type.
            status: Delivery status.
            retry_count: Number of retries.
            error_message: Error message if failed.
            recipient_email: Email address for EMAIL type.

        Returns:
            NotificationStatus instance.
        """
        stat = NotificationStatus.objects.create(
            notification=notification,
            notification_type=notification_type,
            status=status,
            retry_count=retry_count,
            error_message=error_message,
            recipient_email=recipient_email,
        )
        created_statuses.append(stat)

        # Set timestamps based on status
        if status == NotificationStatusEnum.SENT.value:
            stat.sent_at = timezone.now()
            stat.save(update_fields=["sent_at"])
        elif status == NotificationStatusEnum.QUEUED.value:
            stat.queued_at = timezone.now()
            stat.save(update_fields=["queued_at"])
        elif status == NotificationStatusEnum.FAILED.value:
            stat.failed_at = timezone.now()
            stat.save(update_fields=["failed_at"])

        return stat

    yield _create_status

    # Cleanup
    for stat in created_statuses:
        stat.delete()
