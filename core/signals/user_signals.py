"""Django signals for user-related notifications."""

from django.db.models.signals import post_save
from django.dispatch import receiver

import structlog

from core.services.notification_service import notification_service

logger = structlog.get_logger(__name__)


@receiver(post_save, sender="core.User")
def send_welcome_email(
    _sender: type,
    instance,
    created: bool,
    **_kwargs: dict,
) -> None:
    """Send welcome email when a new user is created.

    This signal handler is called after a User is saved. If the user
    is newly created, it sends a welcome email notification.

    Args:
        sender: The model class (User)
        instance: The actual User instance being saved
        created: True if this is a new user, False if updating
        **kwargs: Additional signal arguments
    """
    # Only send email for new users
    if not created:
        return

    try:
        # Create welcome notification
        notification_service.create_notification(
            recipient_email=instance.email,
            subject=f"Welcome to Recipe Web App, {instance.username}!",
            message=f"""
            <html>
            <body>
                <h1>Welcome {instance.username}!</h1>
                <p>Thank you for joining Recipe Web App.</p>
                <p>We're excited to have you as part of our community.</p>
                <p>Start exploring recipes and sharing your own creations!</p>
            </body>
            </html>
            """,
            recipient=instance,
            metadata={
                "event": "user_created",
                "user_id": str(instance.user_id),
                "username": instance.username,
            },
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
