"""Service for handling system-related notifications."""

from django.template.loader import render_to_string

import structlog
from rest_framework.exceptions import PermissionDenied

from core.auth.context import require_current_user
from core.config.downstream_urls import FRONTEND_BASE_URL
from core.exceptions import UserNotFoundError
from core.schemas.notification import (
    BatchNotificationResponse,
    EmailChangedRequest,
    NotificationCreated,
    PasswordResetRequest,
    WelcomeRequest,
)
from core.services.downstream.user_client import user_client
from core.services.notification_service import notification_service

logger = structlog.get_logger(__name__)


class SystemNotificationService:
    """Service for handling system notification business logic."""

    def send_password_reset_notifications(
        self,
        request: PasswordResetRequest,
    ) -> BatchNotificationResponse:
        """Send password reset notification to user.

        Args:
            request: Password reset request with recipient_id, reset_token,
                and expiry_hours

        Returns:
            BatchNotificationResponse with created notification

        Raises:
            UserNotFoundError: If recipient user does not exist
            PermissionDenied: If user lacks admin scope
        """
        # Get authenticated user from security context
        authenticated_user = require_current_user()

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

    def send_welcome_notifications(
        self,
        request: WelcomeRequest,
    ) -> BatchNotificationResponse:
        """Send welcome notifications to newly registered users.

        Args:
            request: Welcome request with recipient_ids

        Returns:
            BatchNotificationResponse with created notifications

        Raises:
            UserNotFoundError: If any recipient user does not exist
            PermissionDenied: If caller is not a service (service-to-service only)
        """
        # Get authenticated user/service from security context
        authenticated_user = require_current_user()

        logger.info(
            "Processing welcome notification request",
            recipient_count=len(request.recipient_ids),
            client_id=authenticated_user.client_id,
        )

        # Verify service-to-service authentication
        # For client_credentials grant, user_id equals client_id
        is_service_to_service = (
            authenticated_user.user_id == authenticated_user.client_id
        )

        if not is_service_to_service:
            logger.warning(
                "Non-service caller attempted to send welcome notifications",
                user_id=authenticated_user.user_id,
                client_id=authenticated_user.client_id,
            )
            raise PermissionDenied(
                detail="Welcome notifications require service-to-service authentication"
            )

        # Process each recipient
        created_notifications: list[NotificationCreated] = []

        for recipient_id in request.recipient_ids:
            # Fetch recipient user details
            try:
                recipient = user_client.get_user(str(recipient_id))
            except UserNotFoundError:
                logger.warning(
                    "Recipient user not found",
                    recipient_id=str(recipient_id),
                )
                raise

            # Determine display name (full name with fallback to username)
            display_name = recipient.full_name or recipient.username

            # Prepare notification data
            subject = "Welcome to Recipe Web App!"
            message = render_to_string(
                "emails/welcome.html",
                {
                    "username": display_name,
                    "app_url": FRONTEND_BASE_URL,
                },
            )

            # Create notification with metadata
            notification = notification_service.create_notification(
                recipient_email=recipient.email,
                subject=subject,
                message=message,
                notification_type="email",
                metadata={
                    "template_type": "welcome",
                    "recipient_id": str(recipient_id),
                },
                auto_queue=True,  # Queue for async processing
            )

            created_notifications.append(
                NotificationCreated(
                    notification_id=notification.notification_id,
                    recipient_id=recipient_id,
                )
            )

            logger.info(
                "Welcome notification created and queued",
                notification_id=str(notification.notification_id),
                recipient_id=str(recipient_id),
            )

        return BatchNotificationResponse(
            notifications=created_notifications,
            queued_count=len(created_notifications),
            message="Notifications queued successfully",
        )

    def send_email_changed_notifications(
        self,
        request: EmailChangedRequest,
    ) -> BatchNotificationResponse:
        """Send email change notifications to old and new addresses.

        Sends security notifications to both the old and new email addresses
        when a user changes their email. This is a security measure to alert
        the user if an unauthorized change was made.

        Args:
            request: Email changed request with recipient_id, old_email, new_email

        Returns:
            BatchNotificationResponse with created notifications (2 notifications)

        Raises:
            UserNotFoundError: If recipient user does not exist
            PermissionDenied: If caller is not a service (service-to-service only)
        """
        # Get authenticated user/service from security context
        authenticated_user = require_current_user()

        logger.info(
            "Processing email changed notification request",
            recipient_count=len(request.recipient_ids),
            client_id=authenticated_user.client_id,
            old_email=request.old_email,
            new_email=request.new_email,
        )

        # Verify service-to-service authentication
        # For client_credentials grant, user_id equals client_id
        is_service_to_service = (
            authenticated_user.user_id == authenticated_user.client_id
        )

        if not is_service_to_service:
            logger.warning(
                "Non-service caller attempted to send email changed notifications",
                user_id=authenticated_user.user_id,
                client_id=authenticated_user.client_id,
            )
            raise PermissionDenied(
                detail=(
                    "Email change notifications require "
                    "service-to-service authentication"
                )
            )

        # Get the single recipient ID
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

        # Determine display name (full name with fallback to username)
        display_name = recipient.full_name or recipient.username

        created_notifications: list[NotificationCreated] = []

        # Create notification for OLD email (security alert)
        subject_old = "Security Alert: Email Address Changed"
        message_old = render_to_string(
            "emails/email_changed.html",
            {
                "recipient_name": display_name,
                "old_email": request.old_email,
                "new_email": request.new_email,
                "is_old_email": True,
                "app_url": FRONTEND_BASE_URL,
            },
        )

        notification_old = notification_service.create_notification(
            recipient_email=request.old_email,
            subject=subject_old,
            message=message_old,
            notification_type="email",
            metadata={
                "template_type": "email_changed",
                "recipient_id": str(recipient_id),
                "old_email": request.old_email,
                "new_email": request.new_email,
                "sent_to": "old_email",
            },
            auto_queue=True,
        )

        created_notifications.append(
            NotificationCreated(
                notification_id=notification_old.notification_id,
                recipient_id=recipient_id,
            )
        )

        logger.info(
            "Email changed notification created for old email",
            notification_id=str(notification_old.notification_id),
            recipient_id=str(recipient_id),
            email=request.old_email,
        )

        # Create notification for NEW email (confirmation)
        subject_new = "Email Address Successfully Changed"
        message_new = render_to_string(
            "emails/email_changed.html",
            {
                "recipient_name": display_name,
                "old_email": request.old_email,
                "new_email": request.new_email,
                "is_old_email": False,
                "app_url": FRONTEND_BASE_URL,
            },
        )

        notification_new = notification_service.create_notification(
            recipient_email=request.new_email,
            subject=subject_new,
            message=message_new,
            notification_type="email",
            metadata={
                "template_type": "email_changed",
                "recipient_id": str(recipient_id),
                "old_email": request.old_email,
                "new_email": request.new_email,
                "sent_to": "new_email",
            },
            auto_queue=True,
        )

        created_notifications.append(
            NotificationCreated(
                notification_id=notification_new.notification_id,
                recipient_id=recipient_id,
            )
        )

        logger.info(
            "Email changed notification created for new email",
            notification_id=str(notification_new.notification_id),
            recipient_id=str(recipient_id),
            email=request.new_email,
        )

        logger.info(
            "All email changed notifications created",
            queued_count=len(created_notifications),
        )

        return BatchNotificationResponse(
            notifications=created_notifications,
            queued_count=len(created_notifications),
            message="Notifications queued successfully",
        )


# Global service instance
system_notification_service = SystemNotificationService()
