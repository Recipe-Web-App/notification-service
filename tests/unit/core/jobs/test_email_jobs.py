"""Tests for email background jobs."""

import smtplib
from datetime import timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from core.jobs.email_jobs import send_email_job
from core.models.notification import Notification


@pytest.mark.django_db
class TestSendEmailJob:
    """Test suite for send_email_job."""

    @pytest.fixture
    def notification(self):
        """Create test notification."""
        return Notification.objects.create(
            recipient_email="test@example.com",
            subject="Test Subject",
            message="<p>Test message</p>",
            status=Notification.QUEUED,
        )

    def test_send_email_job_success(self, notification):
        """Test successful email sending."""
        with patch("core.jobs.email_jobs.EmailService") as mock_email_service:
            mock_service = mock_email_service.return_value
            mock_service.send_email.return_value = True

            send_email_job(str(notification.notification_id))

            notification.refresh_from_db()
            assert notification.status == Notification.SENT
            assert notification.sent_at is not None

    def test_send_email_job_notification_not_found(self):
        """Test job with non-existent notification."""
        fake_id = str(uuid4())

        with pytest.raises(Notification.DoesNotExist):
            send_email_job(fake_id)

    def test_send_email_job_already_sent(self, notification):
        """Test job skips already sent notification."""
        notification.mark_sent()

        with patch("core.jobs.email_jobs.EmailService") as mock_email_service:
            send_email_job(str(notification.notification_id))

            mock_email_service.return_value.send_email.assert_not_called()

    def test_send_email_job_retry_on_failure(self, notification):
        """Test job schedules retry on failure."""
        with patch("core.jobs.email_jobs.EmailService") as mock_email_service:
            mock_service = mock_email_service.return_value
            mock_service.send_email.side_effect = smtplib.SMTPException("SMTP error")

            with patch(
                "core.jobs.email_jobs.django_rq.get_scheduler"
            ) as mock_scheduler:
                mock_scheduler_instance = Mock()
                mock_scheduler.return_value = mock_scheduler_instance

                send_email_job(str(notification.notification_id))

                notification.refresh_from_db()
                assert notification.retry_count == 1
                mock_scheduler_instance.enqueue_in.assert_called_once()

    def test_send_email_job_permanent_failure(self, notification):
        """Test job marks as failed after max retries."""
        notification.retry_count = 3
        notification.save()

        with patch("core.jobs.email_jobs.EmailService") as mock_email_service:
            mock_service = mock_email_service.return_value
            mock_service.send_email.side_effect = smtplib.SMTPException("SMTP error")

            send_email_job(str(notification.notification_id))

            notification.refresh_from_db()
            assert notification.status == Notification.FAILED
            assert notification.failed_at is not None
            assert "Failed after 4 attempts" in notification.error_message

    def test_send_email_job_exponential_backoff(self, notification):
        """Test retry uses exponential backoff."""
        notification.retry_count = 2
        notification.save()

        with patch("core.jobs.email_jobs.EmailService") as mock_email_service:
            mock_service = mock_email_service.return_value
            mock_service.send_email.side_effect = smtplib.SMTPException("SMTP error")

            with patch(
                "core.jobs.email_jobs.django_rq.get_scheduler"
            ) as mock_scheduler:
                mock_scheduler_instance = Mock()
                mock_scheduler.return_value = mock_scheduler_instance

                send_email_job(str(notification.notification_id))

                call_args = mock_scheduler_instance.enqueue_in.call_args
                delay = call_args[0][0]
                assert delay == timedelta(minutes=10)
