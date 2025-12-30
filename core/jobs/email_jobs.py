"""Background jobs for sending email notifications.

This module provides the email job that processes notifications from the queue.
It renders email content from notification_category + notification_data using
the template registry, then sends via the EmailService.
"""

import smtplib
from datetime import timedelta
from uuid import UUID

from django.template.loader import render_to_string

import django_rq
import structlog

from core.models import Notification, NotificationStatus
from core.services.email_service import EmailService
from core.services.notification_templates import EMAIL_TEMPLATES

logger = structlog.get_logger(__name__)


def send_email_job(notification_id: str) -> None:
    """Send an email notification asynchronously.

    This job is executed by RQ workers. It fetches the notification and its
    EMAIL status, renders the email content from the template, sends via
    EmailService, and updates the status accordingly.

    Args:
        notification_id: UUID of the notification to send.

    Raises:
        Notification.DoesNotExist: If notification not found.
        NotificationStatus.DoesNotExist: If EMAIL status not found.
    """
    notification_uuid = UUID(notification_id)

    try:
        notification = Notification.objects.get(notification_id=notification_uuid)
    except Notification.DoesNotExist:
        logger.error(
            "notification_not_found",
            notification_id=notification_id,
        )
        raise

    try:
        email_status = NotificationStatus.objects.get(
            notification_id=notification_uuid,
            notification_type="EMAIL",
        )
    except NotificationStatus.DoesNotExist:
        logger.error(
            "email_status_not_found",
            notification_id=notification_id,
        )
        raise

    if email_status.status == "SENT":
        logger.info(
            "notification_already_sent",
            notification_id=notification_id,
        )
        return

    template_config = EMAIL_TEMPLATES.get(notification.notification_category)
    if not template_config:
        logger.error(
            "template_not_found",
            notification_id=notification_id,
            notification_category=notification.notification_category,
        )
        email_status.mark_failed(
            f"No template found for category: {notification.notification_category}"
        )
        return

    data = notification.notification_data or {}

    try:
        subject = template_config["subject"].format(**data)
    except KeyError as e:
        logger.warning(
            "subject_template_missing_key",
            notification_id=notification_id,
            missing_key=str(e),
        )
        subject = template_config["subject"]

    try:
        html_content = render_to_string(template_config["template"], data)
    except Exception as e:
        logger.error(
            "template_render_failed",
            notification_id=notification_id,
            template=template_config["template"],
            error=str(e),
        )
        email_status.mark_failed(f"Template render failed: {e}")
        return

    if not email_status.recipient_email:
        logger.error(
            "recipient_email_missing",
            notification_id=notification_id,
        )
        email_status.mark_failed("No recipient email address")
        return

    email_service = EmailService()

    try:
        email_service.send_email(
            to_email=email_status.recipient_email,
            subject=subject,
            html_content=html_content,
        )

        email_status.mark_sent()

        logger.info(
            "notification_sent_successfully",
            notification_id=notification_id,
            recipient_email=email_status.recipient_email,
        )

    except (smtplib.SMTPException, ValueError, Exception) as e:
        email_status.increment_retry()

        if email_status.can_retry():
            delay_minutes = 5 * (2 ** ((email_status.retry_count or 1) - 1))
            delay = timedelta(minutes=delay_minutes)

            scheduler = django_rq.get_scheduler("default")
            scheduler.enqueue_in(
                delay,
                send_email_job,
                notification_id,
            )

            logger.warning(
                "notification_send_failed_retry_scheduled",
                notification_id=notification_id,
                retry_count=email_status.retry_count,
                delay_minutes=delay_minutes,
                error=str(e),
            )

        else:
            error_msg = f"Failed after {email_status.retry_count} attempts: {e!s}"
            email_status.mark_failed(error_msg)

            logger.error(
                "notification_send_failed_permanently",
                notification_id=notification_id,
                retry_count=email_status.retry_count,
                error=str(e),
            )
