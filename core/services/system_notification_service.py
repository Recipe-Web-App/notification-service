"""Service for handling system-related notifications."""

import structlog
from rest_framework.exceptions import PermissionDenied

from core.auth.context import require_current_user
from core.config.downstream_urls import FRONTEND_BASE_URL
from core.enums import UserRole
from core.exceptions import UserNotFoundError
from core.models import User
from core.schemas.notification import (
    BatchNotificationResponse,
    EmailChangedRequest,
    MaintenanceRequest,
    NotificationCreated,
    PasswordChangedRequest,
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
                and expiry_hours.

        Returns:
            BatchNotificationResponse with created notification.

        Raises:
            UserNotFoundError: If recipient user does not exist.
            PermissionDenied: If user lacks admin scope.
        """
        authenticated_user = require_current_user()

        logger.info(
            "Processing password reset notification",
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
            expiry_hours=request.expiry_hours,
        )

        has_admin_scope = authenticated_user.has_scope("notification:admin")

        if not has_admin_scope:
            logger.warning(
                "User lacks required scope for password reset notifications",
                user_id=authenticated_user.user_id,
            )
            raise PermissionDenied(detail="Requires notification:admin scope")

        recipient_id = request.recipient_ids[0]

        try:
            recipient = user_client.get_user(str(recipient_id))
        except UserNotFoundError:
            logger.warning(
                "Recipient user not found",
                recipient_id=str(recipient_id),
            )
            raise

        user = User.objects.get(user_id=recipient_id)
        reset_url = f"{FRONTEND_BASE_URL}/reset-password?token={request.reset_token}"

        notification, _ = notification_service.create_notification(
            user=user,
            notification_category="PASSWORD_RESET",
            notification_data={
                "template_version": "1.0",
                "recipient_name": recipient.full_name or recipient.username,
                "reset_url": reset_url,
                "expiry_hours": request.expiry_hours,
                "recipient_id": str(recipient_id),
            },
            recipient_email=recipient.email,
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
            request: Welcome request with recipient_ids.

        Returns:
            BatchNotificationResponse with created notifications.

        Raises:
            UserNotFoundError: If any recipient user does not exist.
            PermissionDenied: If caller is not a service (service-to-service only).
        """
        authenticated_user = require_current_user()

        logger.info(
            "Processing welcome notification request",
            recipient_count=len(request.recipient_ids),
            client_id=authenticated_user.client_id,
        )

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

        created_notifications: list[NotificationCreated] = []

        for recipient_id in request.recipient_ids:
            try:
                recipient = user_client.get_user(str(recipient_id))
            except UserNotFoundError:
                logger.warning(
                    "Recipient user not found",
                    recipient_id=str(recipient_id),
                )
                raise

            user = User.objects.get(user_id=recipient_id)
            display_name = recipient.full_name or recipient.username

            notification, _ = notification_service.create_notification(
                user=user,
                notification_category="WELCOME",
                notification_data={
                    "template_version": "1.0",
                    "username": display_name,
                    "recipient_name": display_name,
                    "app_url": FRONTEND_BASE_URL,
                    "recipient_id": str(recipient_id),
                },
                recipient_email=recipient.email,
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
            request: Email changed request with recipient_id, old_email, new_email.

        Returns:
            BatchNotificationResponse with created notifications (2 notifications).

        Raises:
            UserNotFoundError: If recipient user does not exist.
            PermissionDenied: If caller is not a service (service-to-service only).
        """
        authenticated_user = require_current_user()

        logger.info(
            "Processing email changed notification request",
            recipient_count=len(request.recipient_ids),
            client_id=authenticated_user.client_id,
            old_email=request.old_email,
            new_email=request.new_email,
        )

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

        recipient_id = request.recipient_ids[0]

        try:
            recipient = user_client.get_user(str(recipient_id))
        except UserNotFoundError:
            logger.warning(
                "Recipient user not found",
                recipient_id=str(recipient_id),
            )
            raise

        user = User.objects.get(user_id=recipient_id)
        display_name = recipient.full_name or recipient.username

        created_notifications: list[NotificationCreated] = []

        notification_old, _ = notification_service.create_notification(
            user=user,
            notification_category="EMAIL_CHANGED",
            notification_data={
                "template_version": "1.0",
                "recipient_name": display_name,
                "old_email": request.old_email,
                "new_email": request.new_email,
                "is_old_email": True,
                "app_url": FRONTEND_BASE_URL,
                "recipient_id": str(recipient_id),
                "sent_to": "old_email",
            },
            recipient_email=request.old_email,
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

        notification_new, _ = notification_service.create_notification(
            user=user,
            notification_category="EMAIL_CHANGED",
            notification_data={
                "template_version": "1.0",
                "recipient_name": display_name,
                "old_email": request.old_email,
                "new_email": request.new_email,
                "is_old_email": False,
                "app_url": FRONTEND_BASE_URL,
                "recipient_id": str(recipient_id),
                "sent_to": "new_email",
            },
            recipient_email=request.new_email,
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

    def send_password_changed_notifications(
        self,
        request: PasswordChangedRequest,
    ) -> BatchNotificationResponse:
        """Send password change notifications to users.

        Sends security notifications when users' passwords are changed.
        This is a security measure to alert users of account changes.

        Args:
            request: Password changed request with recipient_ids.

        Returns:
            BatchNotificationResponse with created notifications.

        Raises:
            UserNotFoundError: If any recipient user does not exist.
            PermissionDenied: If caller is not a service (service-to-service only).
        """
        authenticated_user = require_current_user()

        logger.info(
            "Processing password changed notification request",
            recipient_count=len(request.recipient_ids),
            client_id=authenticated_user.client_id,
        )

        is_service_to_service = (
            authenticated_user.user_id == authenticated_user.client_id
        )

        if not is_service_to_service:
            logger.warning(
                "Non-service caller attempted to send password changed notifications",
                user_id=authenticated_user.user_id,
                client_id=authenticated_user.client_id,
            )
            raise PermissionDenied(
                detail=(
                    "Password change notifications require "
                    "service-to-service authentication"
                )
            )

        created_notifications: list[NotificationCreated] = []

        for recipient_id in request.recipient_ids:
            try:
                recipient = user_client.get_user(str(recipient_id))
            except UserNotFoundError:
                logger.warning(
                    "Recipient user not found",
                    recipient_id=str(recipient_id),
                )
                raise

            user = User.objects.get(user_id=recipient_id)
            display_name = recipient.full_name or recipient.username

            notification, _ = notification_service.create_notification(
                user=user,
                notification_category="PASSWORD_CHANGED",
                notification_data={
                    "template_version": "1.0",
                    "recipient_name": display_name,
                    "app_url": FRONTEND_BASE_URL,
                    "recipient_id": str(recipient_id),
                },
                recipient_email=recipient.email,
            )

            created_notifications.append(
                NotificationCreated(
                    notification_id=notification.notification_id,
                    recipient_id=recipient_id,
                )
            )

            logger.info(
                "Password changed notification created and queued",
                notification_id=str(notification.notification_id),
                recipient_id=str(recipient_id),
            )

        logger.info(
            "All password changed notifications created",
            queued_count=len(created_notifications),
        )

        return BatchNotificationResponse(
            notifications=created_notifications,
            queued_count=len(created_notifications),
            message="Notifications queued successfully",
        )

    def send_maintenance_notifications(
        self,
        request: MaintenanceRequest,
    ) -> BatchNotificationResponse:
        """Send maintenance window notifications to users or admins.

        Broadcasts maintenance notifications to all users or only admins
        based on the admin_only flag. Recipients are automatically discovered
        from the database.

        Args:
            request: Maintenance request with start time, end time, description,
                and admin_only flag.

        Returns:
            BatchNotificationResponse with created notifications.

        Raises:
            PermissionDenied: If caller lacks admin scope.
        """
        authenticated_user = require_current_user()

        logger.info(
            "Processing maintenance notification request",
            admin_only=request.admin_only,
            user_id=authenticated_user.user_id,
            maintenance_start=request.maintenance_start.isoformat(),
            maintenance_end=request.maintenance_end.isoformat(),
        )

        has_admin_scope = authenticated_user.has_scope("notification:admin")

        if not has_admin_scope:
            logger.warning(
                "User lacks required scope for maintenance notifications",
                user_id=authenticated_user.user_id,
            )
            raise PermissionDenied(detail="Requires notification:admin scope")

        if request.admin_only:
            recipients = User.objects.filter(
                role=UserRole.ADMIN.value,
                is_active=True,
            )
            logger.info(
                "Broadcasting maintenance notification to admins only",
                admin_count=recipients.count(),
            )
        else:
            recipients = User.objects.filter(is_active=True)
            logger.info(
                "Broadcasting maintenance notification to all users",
                user_count=recipients.count(),
            )

        created_notifications: list[NotificationCreated] = []

        for recipient in recipients:
            display_name = recipient.full_name or recipient.username

            notification, _ = notification_service.create_notification(
                user=recipient,
                notification_category="MAINTENANCE",
                notification_data={
                    "template_version": "1.0",
                    "recipient_name": display_name,
                    "maintenance_start": request.maintenance_start.isoformat(),
                    "maintenance_end": request.maintenance_end.isoformat(),
                    "description": request.description,
                    "app_url": FRONTEND_BASE_URL,
                    "recipient_id": str(recipient.user_id),
                    "admin_only": request.admin_only,
                },
                recipient_email=recipient.email,
            )

            created_notifications.append(
                NotificationCreated(
                    notification_id=notification.notification_id,
                    recipient_id=recipient.user_id,
                )
            )

            logger.debug(
                "Maintenance notification created and queued",
                notification_id=str(notification.notification_id),
                recipient_id=str(recipient.user_id),
            )

        logger.info(
            "All maintenance notifications created",
            queued_count=len(created_notifications),
        )

        return BatchNotificationResponse(
            notifications=created_notifications,
            queued_count=len(created_notifications),
            message="Notifications queued successfully",
        )


system_notification_service = SystemNotificationService()
