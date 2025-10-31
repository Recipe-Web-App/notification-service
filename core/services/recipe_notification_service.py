"""Service for handling recipe-related notifications."""

from django.template.loader import render_to_string

import structlog
from rest_framework.exceptions import PermissionDenied

from core.auth.oauth2 import OAuth2User
from core.config.downstream_urls import FRONTEND_BASE_URL
from core.exceptions import CommentNotFoundError, RecipeNotFoundError
from core.schemas.notification import (
    BatchNotificationResponse,
    NotificationCreated,
    RecipeCommentedRequest,
    RecipeLikedRequest,
    RecipePublishedRequest,
)
from core.services.downstream.recipe_management_service_client import (
    recipe_management_service_client,
)
from core.services.downstream.user_client import user_client
from core.services.notification_service import notification_service

logger = structlog.get_logger(__name__)


class RecipeNotificationService:
    """Service for handling recipe notification business logic."""

    def send_recipe_published_notifications(
        self,
        request: RecipePublishedRequest,
        authenticated_user: OAuth2User,
    ) -> BatchNotificationResponse:
        """Send notifications when a recipe is published.

        Args:
            request: Recipe published request with recipient_ids and recipe_id
            authenticated_user: Authenticated OAuth2 user

        Returns:
            BatchNotificationResponse with created notifications

        Raises:
            RecipeNotFoundError: If recipe does not exist
            PermissionDenied: If user lacks permission to notify recipients
        """
        logger.info(
            "Processing recipe published notifications",
            recipe_id=str(request.recipe_id),
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
        )

        # Fetch recipe details from recipe-management service
        try:
            recipe = recipe_management_service_client.get_recipe(int(request.recipe_id))
        except RecipeNotFoundError:
            logger.warning(
                "Recipe not found",
                recipe_id=str(request.recipe_id),
            )
            raise

        # Authorization logic
        has_admin_scope = authenticated_user.has_scope("notification:admin")

        if not has_admin_scope:
            # If user doesn't have admin scope, validate follower
            # relationships
            logger.info(
                "Validating follower relationships for user scope",
                user_id=authenticated_user.user_id,
                author_id=recipe.user_id,
            )

            # Check if each recipient follows the recipe author
            author_id = str(recipe.user_id)
            invalid_recipients = []

            for recipient_id in request.recipient_ids:
                recipient_id_str = str(recipient_id)
                is_follower = user_client.validate_follower_relationship(
                    follower_id=recipient_id_str,
                    followee_id=author_id,
                )

                if not is_follower:
                    invalid_recipients.append(recipient_id_str)

            if invalid_recipients:
                logger.warning(
                    "Invalid follower relationships detected",
                    invalid_recipients=invalid_recipients,
                    author_id=author_id,
                )
                raise PermissionDenied(
                    detail=(
                        "One or more recipients are not followers of the recipe author"
                    )
                )

        # Fetch author details for email personalization
        author = user_client.get_user(str(recipe.user_id))

        # Construct recipe URL
        recipe_url = f"{FRONTEND_BASE_URL}/recipes/{request.recipe_id}"

        # Create notifications for each recipient
        created_notifications = []

        for recipient_id in request.recipient_ids:
            # Fetch recipient details
            recipient = user_client.get_user(str(recipient_id))

            # Prepare notification data
            subject = f"New Recipe: {recipe.title}"
            message = render_to_string(
                "emails/recipe_published.html",
                {
                    "recipient_name": (recipient.full_name or recipient.username),
                    "author_name": author.full_name or author.username,
                    "recipe_title": recipe.title,
                    "recipe_url": recipe_url,
                },
            )

            # Create notification with metadata
            notification = notification_service.create_notification(
                recipient_email=recipient.email,
                subject=subject,
                message=message,
                notification_type="email",
                metadata={
                    "template_type": "recipe_published",
                    "recipe_id": str(request.recipe_id),
                    "author_id": str(recipe.user_id),
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
            "All recipe published notifications created",
            queued_count=len(created_notifications),
        )

        return BatchNotificationResponse(
            notifications=created_notifications,
            queued_count=len(created_notifications),
            message="Notifications queued successfully",
        )

    def send_recipe_liked_notifications(
        self,
        request: RecipeLikedRequest,
        authenticated_user: OAuth2User,
    ) -> BatchNotificationResponse:
        """Send notifications when a recipe is liked.

        Args:
            request: Recipe liked request with recipient_ids, recipe_id,
                and liker_id
            authenticated_user: Authenticated OAuth2 user

        Returns:
            BatchNotificationResponse with created notifications

        Raises:
            RecipeNotFoundError: If recipe does not exist
            PermissionDenied: If user lacks permission to notify recipients
        """
        logger.info(
            "Processing recipe liked notifications",
            recipe_id=str(request.recipe_id),
            liker_id=str(request.liker_id),
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
        )

        # Fetch recipe details from recipe-management service
        try:
            recipe = recipe_management_service_client.get_recipe(int(request.recipe_id))
        except RecipeNotFoundError:
            logger.warning(
                "Recipe not found",
                recipe_id=str(request.recipe_id),
            )
            raise

        # Authorization logic
        has_admin_scope = authenticated_user.has_scope("notification:admin")

        if not has_admin_scope:
            # If user doesn't have admin scope, validate that the liker
            # follows the recipe author
            logger.info(
                "Validating follower relationship for user scope",
                user_id=authenticated_user.user_id,
                liker_id=str(request.liker_id),
                author_id=str(recipe.user_id),
            )

            # Check if liker follows the recipe author
            author_id = str(recipe.user_id)
            liker_id = str(request.liker_id)

            is_follower = user_client.validate_follower_relationship(
                follower_id=liker_id,
                followee_id=author_id,
            )

            if not is_follower:
                logger.warning(
                    "Invalid follower relationship detected",
                    liker_id=liker_id,
                    author_id=author_id,
                )
                raise PermissionDenied(
                    detail="Liker is not a follower of the recipe author"
                )

        # Fetch liker details for email personalization
        liker = user_client.get_user(str(request.liker_id))

        # Construct recipe URL
        recipe_url = f"{FRONTEND_BASE_URL}/recipes/{request.recipe_id}"

        # Create notifications for each recipient
        created_notifications = []

        for recipient_id in request.recipient_ids:
            # Fetch recipient details
            recipient = user_client.get_user(str(recipient_id))

            # Prepare notification data
            subject = (
                f"{liker.full_name or liker.username} liked your recipe: {recipe.title}"
            )
            message = render_to_string(
                "emails/recipe_liked.html",
                {
                    "recipient_name": (recipient.full_name or recipient.username),
                    "liker_name": liker.full_name or liker.username,
                    "recipe_title": recipe.title,
                    "recipe_url": recipe_url,
                },
            )

            # Create notification with metadata
            notification = notification_service.create_notification(
                recipient_email=recipient.email,
                subject=subject,
                message=message,
                notification_type="email",
                metadata={
                    "template_type": "recipe_liked",
                    "recipe_id": str(request.recipe_id),
                    "liker_id": str(request.liker_id),
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
            "All recipe liked notifications created",
            queued_count=len(created_notifications),
        )

        return BatchNotificationResponse(
            notifications=created_notifications,
            queued_count=len(created_notifications),
            message="Notifications queued successfully",
        )

    def send_recipe_commented_notifications(
        self,
        request: RecipeCommentedRequest,
        authenticated_user: OAuth2User,
    ) -> BatchNotificationResponse:
        """Send notifications when a recipe is commented on.

        Args:
            request: Recipe commented request with recipient_ids and comment_id
            authenticated_user: Authenticated OAuth2 user

        Returns:
            BatchNotificationResponse with created notifications

        Raises:
            CommentNotFoundError: If comment does not exist
            RecipeNotFoundError: If recipe does not exist
            PermissionDenied: If user lacks permission to notify recipients
        """
        logger.info(
            "Processing recipe commented notifications",
            comment_id=str(request.comment_id),
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
        )

        # Fetch comment details from recipe-management service
        try:
            comment = recipe_management_service_client.get_comment(
                str(request.comment_id)
            )
        except CommentNotFoundError:
            logger.warning(
                "Comment not found",
                comment_id=str(request.comment_id),
            )
            raise

        # Fetch recipe details using comment.recipe_id
        try:
            recipe = recipe_management_service_client.get_recipe(comment.recipe_id)
        except RecipeNotFoundError:
            logger.warning(
                "Recipe not found",
                recipe_id=comment.recipe_id,
            )
            raise

        # Authorization logic
        has_admin_scope = authenticated_user.has_scope("notification:admin")

        if not has_admin_scope:
            # If user doesn't have admin scope, validate that the commenter
            # follows the recipe author
            logger.info(
                "Validating follower relationship for user scope",
                user_id=authenticated_user.user_id,
                commenter_id=str(comment.user_id),
                author_id=str(recipe.user_id),
            )

            # Check if commenter follows the recipe author
            author_id = str(recipe.user_id)
            commenter_id = str(comment.user_id)

            is_follower = user_client.validate_follower_relationship(
                follower_id=commenter_id,
                followee_id=author_id,
            )

            if not is_follower:
                logger.warning(
                    "Invalid follower relationship detected",
                    commenter_id=commenter_id,
                    author_id=author_id,
                )
                raise PermissionDenied(
                    detail="Commenter is not a follower of the recipe author"
                )

        # Fetch commenter details for email personalization
        commenter = user_client.get_user(str(comment.user_id))

        # Construct recipe URL
        recipe_url = f"{FRONTEND_BASE_URL}/recipes/{comment.recipe_id}"

        # Prepare comment preview (truncate if too long)
        comment_preview = comment.comment_text
        if len(comment_preview) > 150:
            comment_preview = comment_preview[:150] + "..."

        # Create notifications for each recipient
        created_notifications = []

        for recipient_id in request.recipient_ids:
            # Fetch recipient details
            recipient = user_client.get_user(str(recipient_id))

            # Prepare notification data
            subject = (
                f"{commenter.full_name or commenter.username} "
                f"commented on your recipe: {recipe.title}"
            )
            message = render_to_string(
                "emails/recipe_commented.html",
                {
                    "recipient_name": (recipient.full_name or recipient.username),
                    "commenter_name": commenter.full_name or commenter.username,
                    "recipe_title": recipe.title,
                    "comment_preview": comment_preview,
                    "recipe_url": recipe_url,
                },
            )

            # Create notification with metadata
            notification = notification_service.create_notification(
                recipient_email=recipient.email,
                subject=subject,
                message=message,
                notification_type="email",
                metadata={
                    "template_type": "recipe_commented",
                    "comment_id": str(request.comment_id),
                    "recipe_id": str(comment.recipe_id),
                    "commenter_id": str(comment.user_id),
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
            "All recipe commented notifications created",
            queued_count=len(created_notifications),
        )

        return BatchNotificationResponse(
            notifications=created_notifications,
            queued_count=len(created_notifications),
            message="Notifications queued successfully",
        )


# Global service instance
recipe_notification_service = RecipeNotificationService()
