"""Django signals for user-related notifications."""

from django.db.models.signals import post_save
from django.dispatch import receiver

import structlog

from core.models.user import User
from core.services.notification_service import notification_service

logger = structlog.get_logger(__name__)


@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs) -> None:
    """Send welcome email when a new user is created.

    This signal handler is called after a User is saved. If the user
    is newly created, it sends a welcome email notification.

    Args:
        sender: The model class (User).
        instance: The actual User instance being saved.
        created: True if this is a new user, False if updating.
        **kwargs: Additional signal arguments.
    """
    del sender, kwargs  # Mark as used
    # Only send email for new users
    if not created:
        return

    try:
        # Create welcome notification using new two-table design
        notification_service.create_notification(
            user=instance,
            notification_category="WELCOME",
            notification_data={
                "template_version": "1.0",
                "username": instance.username,
            },
            recipient_email=instance.email,
        )

        logger.info(
            "welcome_email_queued",
            user_id=str(instance.user_id),
            email=instance.email,
        )

    except Exception as e:
        # Don't let email failures break user creation
        logger.error(
            "welcome_email_failed",
            user_id=str(instance.user_id),
            email=instance.email,
            error=str(e),
        )
