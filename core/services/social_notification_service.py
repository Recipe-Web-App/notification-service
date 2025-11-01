"""Service for handling social-related notifications."""

from django.template.loader import render_to_string

import structlog
from rest_framework.exceptions import PermissionDenied

from core.auth.oauth2 import OAuth2User
from core.config.downstream_urls import FRONTEND_BASE_URL
from core.exceptions import UserNotFoundError
from core.schemas.notification import (
    BatchNotificationResponse,
    NewFollowerRequest,
    NotificationCreated,
)
from core.services.downstream.recipe_management_service_client import (
    recipe_management_service_client,
)
from core.services.downstream.user_client import user_client
from core.services.notification_service import notification_service

logger = structlog.get_logger(__name__)


class SocialNotificationService:
    """Service for handling social notification business logic."""

    def send_new_follower_notifications(
        self,
        request: NewFollowerRequest,
        authenticated_user: OAuth2User,
    ) -> BatchNotificationResponse:
        """Send notifications when a user gains a new follower.

        Args:
            request: New follower request with recipient_ids and follower_id
            authenticated_user: Authenticated OAuth2 user

        Returns:
            BatchNotificationResponse with created notifications

        Raises:
            UserNotFoundError: If follower or recipient user does not exist
            PermissionDenied: If user lacks admin scope or relationship
                does not exist
        """
        logger.info(
            "Processing new follower notifications",
            follower_id=str(request.follower_id),
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
        )

        # Check for admin scope (required per OpenAPI spec)
        has_admin_scope = authenticated_user.has_scope("notification:admin")

        if not has_admin_scope:
            logger.warning(
                "User lacks notification:admin scope for new follower",
                user_id=authenticated_user.user_id,
            )
            raise PermissionDenied(detail="Requires notification:admin scope")

        # Fetch follower details
        try:
            follower = user_client.get_user(str(request.follower_id))
        except UserNotFoundError:
            logger.warning(
                "Follower user not found",
                follower_id=str(request.follower_id),
            )
            raise

        # Validate follower relationship exists for each recipient
        logger.info(
            "Validating follower relationships exist",
            follower_id=str(request.follower_id),
        )

        for recipient_id in request.recipient_ids:
            recipient_id_str = str(recipient_id)
            is_follower = user_client.validate_follower_relationship(
                follower_id=str(request.follower_id),
                followee_id=recipient_id_str,
            )

            if not is_follower:
                logger.warning(
                    "Follower relationship does not exist",
                    follower_id=str(request.follower_id),
                    followee_id=recipient_id_str,
                )
                raise PermissionDenied(
                    detail=(
                        f"Follower relationship between "
                        f"{request.follower_id} and {recipient_id} "
                        f"does not exist"
                    )
                )

        # Fetch follower's recipe count
        recipe_count = recipe_management_service_client.get_user_recipe_count(
            str(request.follower_id)
        )

        # Construct profile and recipes URLs
        profile_url = f"{FRONTEND_BASE_URL}/users/{follower.username}"
        recipes_url = f"{FRONTEND_BASE_URL}/users/{follower.username}/recipes"

        # Create notifications for each recipient
        created_notifications = []

        for recipient_id in request.recipient_ids:
            # Fetch recipient details
            try:
                recipient = user_client.get_user(str(recipient_id))
            except UserNotFoundError:
                logger.warning(
                    "Recipient user not found",
                    recipient_id=str(recipient_id),
                )
                raise

            # Prepare notification data
            subject = f"{follower.full_name or follower.username} is now following you"
            message = render_to_string(
                "emails/new_follower.html",
                {
                    "recipient_name": (recipient.full_name or recipient.username),
                    "follower_name": follower.full_name or follower.username,
                    "follower_username": follower.username,
                    "follower_bio": follower.bio if hasattr(follower, "bio") else None,
                    "recipe_count": recipe_count,
                    "profile_url": profile_url,
                    "recipes_url": recipes_url,
                },
            )

            # Create notification with metadata
            notification = notification_service.create_notification(
                recipient_email=recipient.email,
                subject=subject,
                message=message,
                notification_type="email",
                metadata={
                    "template_type": "new_follower",
                    "follower_id": str(request.follower_id),
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
                "Notification created and queued",
                notification_id=str(notification.notification_id),
                recipient_id=str(recipient_id),
            )

        logger.info(
            "All new follower notifications created",
            queued_count=len(created_notifications),
        )

        return BatchNotificationResponse(
            notifications=created_notifications,
            queued_count=len(created_notifications),
            message="Notifications queued successfully",
        )


# Global service instance
social_notification_service = SocialNotificationService()
