"""Background jobs for sending email notifications."""

import smtplib
from datetime import timedelta
from uuid import UUID

import django_rq
import structlog

from core.models.notification import Notification
from core.services.email_service import EmailService

logger = structlog.get_logger(__name__)


def send_email_job(notification_id: str) -> None:
    """Send an email notification asynchronously.

    This job is executed by RQ workers. It sends the email and updates
    the notification status. If sending fails, it schedules a retry with
    exponential backoff.

    Args:
        notification_id: UUID of the notification to send

    Raises:
        Notification.DoesNotExist: If notification not found
    """
    # Convert string to UUID
    notification_uuid = UUID(notification_id)

    # Get notification
    try:
        notification = Notification.objects.get(notification_id=notification_uuid)
    except Notification.DoesNotExist:
        logger.error(
            "notification_not_found",
            notification_id=notification_id,
        )
        raise

    # Skip if already sent
    if notification.status == Notification.SENT:
        logger.info(
            "notification_already_sent",
            notification_id=notification_id,
        )
        return

    # Initialize email service
    email_service = EmailService()

    try:
        # Send email
        email_service.send_email(
            to_email=notification.recipient_email,
            subject=notification.subject,
            html_content=notification.message,
        )

        # Mark as sent
        notification.mark_sent()

        logger.info(
            "notification_sent_successfully",
            notification_id=notification_id,
            recipient_email=notification.recipient_email,
        )

    except (smtplib.SMTPException, ValueError, Exception) as e:
        # Increment retry count
        notification.increment_retry()

        # Check if we can retry
        if notification.can_retry():
            # Calculate delay with exponential backoff
            # Delay = 5 * (2 ** (retry_count - 1)) minutes
            delay_minutes = 5 * (2 ** (notification.retry_count - 1))
            delay = timedelta(minutes=delay_minutes)

            # Schedule retry
            scheduler = django_rq.get_scheduler("default")
            scheduler.enqueue_in(
                delay,
                send_email_job,
                notification_id,
            )

            logger.warning(
                "notification_send_failed_retry_scheduled",
                notification_id=notification_id,
                retry_count=notification.retry_count,
                delay_minutes=delay_minutes,
                error=str(e),
            )

        else:
            # Mark as permanently failed
            error_msg = f"Failed after {notification.retry_count} attempts: {e!s}"
            notification.mark_failed(error_msg)

            logger.error(
                "notification_send_failed_permanently",
                notification_id=notification_id,
                retry_count=notification.retry_count,
                error=str(e),
            )
