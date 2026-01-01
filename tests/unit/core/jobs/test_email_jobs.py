"""Tests for email background jobs with two-table schema."""

import smtplib
from datetime import timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

from django.db.models.signals import post_save

import pytest

from core.enums.notification import (
    NotificationCategory,
    NotificationStatusEnum,
    NotificationType,
)
from core.jobs.email_jobs import send_email_job
from core.models.notification import Notification
from core.models.notification_status import NotificationStatus
from core.models.user import User
from core.signals.user_signals import send_welcome_email


@pytest.mark.django_db
class TestSendEmailJob:
    """Test suite for send_email_job with two-table schema."""

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
    def notification_with_email_status(self, user):
        """Create notification with EMAIL status for testing."""
        notification = Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={
                "template_version": "1.0",
                "actor_name": "John",
                "recipe_title": "Test Recipe",
            },
        )
        email_status = NotificationStatus.objects.create(
            notification=notification,
            notification_type=NotificationType.EMAIL.value,
            status=NotificationStatusEnum.QUEUED.value,
            recipient_email=user.email,
        )
        return notification, email_status

    def test_send_email_job_success(self, notification_with_email_status):
        """Test successful email sending updates NotificationStatus."""
        notification, email_status = notification_with_email_status

        with patch("core.jobs.email_jobs.EmailService") as mock_email_service:
            mock_service = mock_email_service.return_value
            mock_service.send_email.return_value = True

            with patch("core.jobs.email_jobs.render_to_string") as mock_render:
                mock_render.return_value = "<p>Test email content</p>"

                send_email_job(str(notification.notification_id))

                email_status.refresh_from_db()
                assert email_status.status == NotificationStatusEnum.SENT.value
                assert email_status.sent_at is not None
                mock_service.send_email.assert_called_once()

    def test_send_email_job_notification_not_found(self):
        """Test job with non-existent notification raises error."""
        fake_id = str(uuid4())

        with pytest.raises(Notification.DoesNotExist):
            send_email_job(fake_id)

    def test_send_email_job_email_status_not_found(self, user):
        """Test job with missing EMAIL status raises error."""
        notification = Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={"template_version": "1.0"},
        )

        with pytest.raises(NotificationStatus.DoesNotExist):
            send_email_job(str(notification.notification_id))

    def test_send_email_job_already_sent(self, notification_with_email_status):
        """Test job skips already sent notification."""
        notification, email_status = notification_with_email_status

        email_status.status = NotificationStatusEnum.SENT.value
        email_status.save()

        with patch("core.jobs.email_jobs.EmailService") as mock_email_service:
            send_email_job(str(notification.notification_id))

            mock_email_service.return_value.send_email.assert_not_called()

    def test_send_email_job_retry_on_failure(self, notification_with_email_status):
        """Test job schedules retry on SMTP failure."""
        notification, email_status = notification_with_email_status

        with patch("core.jobs.email_jobs.EmailService") as mock_email_service:
            mock_service = mock_email_service.return_value
            mock_service.send_email.side_effect = smtplib.SMTPException("SMTP error")

            with patch("core.jobs.email_jobs.render_to_string") as mock_render:
                mock_render.return_value = "<p>Test content</p>"

                with patch(
                    "core.jobs.email_jobs.django_rq.get_scheduler"
                ) as mock_scheduler:
                    mock_scheduler_instance = Mock()
                    mock_scheduler.return_value = mock_scheduler_instance

                    send_email_job(str(notification.notification_id))

                    email_status.refresh_from_db()
                    assert email_status.retry_count == 1
                    mock_scheduler_instance.enqueue_in.assert_called_once()

    def test_send_email_job_permanent_failure(self, notification_with_email_status):
        """Test job marks as failed after max retries."""
        notification, email_status = notification_with_email_status

        email_status.retry_count = 3
        email_status.save()

        with patch("core.jobs.email_jobs.EmailService") as mock_email_service:
            mock_service = mock_email_service.return_value
            mock_service.send_email.side_effect = smtplib.SMTPException("SMTP error")

            with patch("core.jobs.email_jobs.render_to_string") as mock_render:
                mock_render.return_value = "<p>Test content</p>"

                send_email_job(str(notification.notification_id))

                email_status.refresh_from_db()
                assert email_status.status == NotificationStatusEnum.FAILED.value
                assert email_status.failed_at is not None
                assert "Failed after" in email_status.error_message

    def test_send_email_job_exponential_backoff(self, notification_with_email_status):
        """Test retry uses exponential backoff timing."""
        notification, email_status = notification_with_email_status

        email_status.retry_count = 1
        email_status.save()

        with patch("core.jobs.email_jobs.EmailService") as mock_email_service:
            mock_service = mock_email_service.return_value
            mock_service.send_email.side_effect = smtplib.SMTPException("SMTP error")

            with patch("core.jobs.email_jobs.render_to_string") as mock_render:
                mock_render.return_value = "<p>Test content</p>"

                with patch(
                    "core.jobs.email_jobs.django_rq.get_scheduler"
                ) as mock_scheduler:
                    mock_scheduler_instance = Mock()
                    mock_scheduler.return_value = mock_scheduler_instance

                    send_email_job(str(notification.notification_id))

                    mock_scheduler_instance.enqueue_in.assert_called_once()
                    call_args = mock_scheduler_instance.enqueue_in.call_args
                    delay = call_args[0][0]
                    assert delay == timedelta(minutes=10)

    def test_send_email_job_template_not_found(self, user):
        """Test job handles missing template gracefully."""
        notification = Notification.objects.create(
            user=user,
            notification_category="INVALID_CATEGORY",
            notification_data={"template_version": "1.0"},
        )
        email_status = NotificationStatus.objects.create(
            notification=notification,
            notification_type=NotificationType.EMAIL.value,
            status=NotificationStatusEnum.QUEUED.value,
            recipient_email=user.email,
        )

        send_email_job(str(notification.notification_id))

        email_status.refresh_from_db()
        assert email_status.status == NotificationStatusEnum.FAILED.value
        assert "No template found" in email_status.error_message

    def test_send_email_job_template_render_error(self, notification_with_email_status):
        """Test job handles template render failure."""
        notification, email_status = notification_with_email_status

        with patch("core.jobs.email_jobs.render_to_string") as mock_render:
            mock_render.side_effect = Exception("Template error")

            send_email_job(str(notification.notification_id))

            email_status.refresh_from_db()
            assert email_status.status == NotificationStatusEnum.FAILED.value
            assert "Template render failed" in email_status.error_message

    def test_send_email_job_missing_recipient_email(self, user):
        """Test job handles missing recipient email."""
        notification = Notification.objects.create(
            user=user,
            notification_category=NotificationCategory.RECIPE_LIKED.value,
            notification_data={
                "template_version": "1.0",
                "actor_name": "John",
            },
        )
        email_status = NotificationStatus.objects.create(
            notification=notification,
            notification_type=NotificationType.EMAIL.value,
            status=NotificationStatusEnum.QUEUED.value,
            recipient_email=None,
        )

        with patch("core.jobs.email_jobs.render_to_string") as mock_render:
            mock_render.return_value = "<p>Test content</p>"

            send_email_job(str(notification.notification_id))

            email_status.refresh_from_db()
            assert email_status.status == NotificationStatusEnum.FAILED.value
            assert "No recipient email" in email_status.error_message

    def test_send_email_job_subject_formatting(self, notification_with_email_status):
        """Test job formats subject with notification data."""
        notification, _email_status = notification_with_email_status

        with patch("core.jobs.email_jobs.EmailService") as mock_email_service:
            mock_service = mock_email_service.return_value
            mock_service.send_email.return_value = True

            with patch("core.jobs.email_jobs.render_to_string") as mock_render:
                mock_render.return_value = "<p>Test content</p>"

                send_email_job(str(notification.notification_id))

                call_args = mock_service.send_email.call_args
                assert call_args.kwargs["subject"] == "John liked your recipe"
