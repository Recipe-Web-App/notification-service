"""Service for handling system-related notifications."""

from django.template.loader import render_to_string

import structlog
from rest_framework.exceptions import PermissionDenied

from core.auth.oauth2 import OAuth2User
from core.config.downstream_urls import FRONTEND_BASE_URL
from core.exceptions import UserNotFoundError
from core.schemas.notification import (
    BatchNotificationResponse,
    NotificationCreated,
    PasswordResetRequest,
)
from core.services.downstream.user_client import user_client
from core.services.notification_service import notification_service

logger = structlog.get_logger(__name__)


class SystemNotificationService:
    """Service for handling system notification business logic."""

    def send_password_reset_notifications(
        self,
        request: PasswordResetRequest,
        authenticated_user: OAuth2User,
    ) -> BatchNotificationResponse:
        """Send password reset notification to user.

        Args:
            request: Password reset request with recipient_id, reset_token,
                and expiry_hours
            authenticated_user: Authenticated OAuth2 user

        Returns:
            BatchNotificationResponse with created notification

        Raises:
            UserNotFoundError: If recipient user does not exist
            PermissionDenied: If user lacks admin scope
        """
        logger.info(
            "Processing password reset notification",
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
            expiry_hours=request.expiry_hours,
        )

        # Check for admin scope (required per OpenAPI spec)
        has_admin_scope = authenticated_user.has_scope("notification:admin")

        if not has_admin_scope:
            logger.warning(
                "User lacks required scope for password reset notifications",
                user_id=authenticated_user.user_id,
            )
            raise PermissionDenied(detail="Requires notification:admin scope")

        # Get recipient ID (only one allowed)
        recipient_id = request.recipient_ids[0]

        # Fetch recipient user details
        try:
            recipient = user_client.get_user(str(recipient_id))
        except UserNotFoundError:
            logger.warning(
                "Recipient user not found",
                recipient_id=str(recipient_id),
            )
            raise

        # Construct password reset URL with token
        reset_url = f"{FRONTEND_BASE_URL}/reset-password?token={request.reset_token}"

        # Prepare notification data
        subject = "Reset Your Password - Recipe Web App"
        message = render_to_string(
            "emails/password_reset.html",
            {
                "recipient_name": recipient.full_name or recipient.username,
                "reset_url": reset_url,
                "expiry_hours": request.expiry_hours,
            },
        )

        # Create notification with metadata
        notification = notification_service.create_notification(
            recipient_email=recipient.email,
            subject=subject,
            message=message,
            notification_type="email",
            metadata={
                "template_type": "password_reset",
                "recipient_id": str(recipient_id),
                "expiry_hours": request.expiry_hours,
            },
            auto_queue=True,  # Queue for async processing
        )

        created_notification = NotificationCreated(
            notification_id=notification.notification_id,
            recipient_id=recipient_id,
        )

        logger.info(
            "Password reset notification created and queued",
            notification_id=str(notification.notification_id),
            recipient_id=str(recipient_id),
        )

        return BatchNotificationResponse(
            notifications=[created_notification],
            queued_count=1,
            message="Notifications queued successfully",
        )


# Global service instance
system_notification_service = SystemNotificationService()
