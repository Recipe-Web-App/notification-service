"""Tests for email background jobs."""

import smtplib
from datetime import timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import TestCase

from core.jobs.email_jobs import send_email_job
from core.models.notification import Notification


class TestSendEmailJob(TestCase):
    """Test suite for send_email_job."""

    def setUp(self):
        """Set up test fixtures."""
        self.notification = Notification.objects.create(
            recipient_email="test@example.com",
            subject="Test Subject",
            message="<p>Test message</p>",
            status=Notification.QUEUED,
        )

    def test_send_email_job_success(self):
        """Test successful email sending."""
        with patch("core.jobs.email_jobs.EmailService") as mock_email_service:
            mock_service = mock_email_service.return_value
            mock_service.send_email.return_value = True

            send_email_job(str(self.notification.notification_id))

            self.notification.refresh_from_db()
            self.assertEqual(self.notification.status, Notification.SENT)
            self.assertIsNotNone(self.notification.sent_at)

    def test_send_email_job_notification_not_found(self):
        """Test job with non-existent notification."""
        fake_id = str(uuid4())

        with self.assertRaises(Notification.DoesNotExist):
            send_email_job(fake_id)

    def test_send_email_job_already_sent(self):
        """Test job skips already sent notification."""
        self.notification.mark_sent()

        with patch("core.jobs.email_jobs.EmailService") as mock_email_service:
            send_email_job(str(self.notification.notification_id))

            mock_email_service.return_value.send_email.assert_not_called()

    def test_send_email_job_retry_on_failure(self):
        """Test job schedules retry on failure."""
        with patch("core.jobs.email_jobs.EmailService") as mock_email_service:
            mock_service = mock_email_service.return_value
            mock_service.send_email.side_effect = smtplib.SMTPException("SMTP error")

            with patch(
                "core.jobs.email_jobs.django_rq.get_scheduler"
            ) as mock_scheduler:
                mock_scheduler_instance = Mock()
                mock_scheduler.return_value = mock_scheduler_instance

                send_email_job(str(self.notification.notification_id))

                self.notification.refresh_from_db()
                self.assertEqual(self.notification.retry_count, 1)
                mock_scheduler_instance.enqueue_in.assert_called_once()

    def test_send_email_job_permanent_failure(self):
        """Test job marks as failed after max retries."""
        self.notification.retry_count = 3
        self.notification.save()

        with patch("core.jobs.email_jobs.EmailService") as mock_email_service:
            mock_service = mock_email_service.return_value
            mock_service.send_email.side_effect = smtplib.SMTPException("SMTP error")

            send_email_job(str(self.notification.notification_id))

            self.notification.refresh_from_db()
            self.assertEqual(self.notification.status, Notification.FAILED)
            self.assertIsNotNone(self.notification.failed_at)
            self.assertIn("Failed after 4 attempts", self.notification.error_message)

    def test_send_email_job_exponential_backoff(self):
        """Test retry uses exponential backoff."""
        # Start with retry_count=1, so after increment it becomes 2
        # With max_retries=3, this allows one more retry
        # Delay should be: 5 * (2 ** (2 - 1)) = 5 * 2 = 10 minutes
        self.notification.retry_count = 1
        self.notification.save()

        with patch("core.jobs.email_jobs.EmailService") as mock_email_service:
            mock_service = mock_email_service.return_value
            mock_service.send_email.side_effect = smtplib.SMTPException("SMTP error")

            with patch(
                "core.jobs.email_jobs.django_rq.get_scheduler"
            ) as mock_scheduler:
                mock_scheduler_instance = Mock()
                mock_scheduler.return_value = mock_scheduler_instance

                send_email_job(str(self.notification.notification_id))

                # Verify enqueue_in was called for retry
                mock_scheduler_instance.enqueue_in.assert_called_once()
                call_args = mock_scheduler_instance.enqueue_in.call_args
                delay = call_args[0][0]
                self.assertEqual(delay, timedelta(minutes=10))
