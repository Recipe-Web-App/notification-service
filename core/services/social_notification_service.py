"""Service for handling social-related notifications."""

from uuid import UUID

import structlog
from rest_framework.exceptions import PermissionDenied

from core.auth.context import require_current_user
from core.auth.oauth2 import OAuth2User
from core.config.downstream_urls import FRONTEND_BASE_URL
from core.exceptions import (
    CollectionNotFoundError,
    CommentNotFoundError,
    RecipeNotFoundError,
    UserNotFoundError,
)
from core.models import User
from core.schemas.notification import (
    BatchNotificationResponse,
    MentionRequest,
    NewFollowerRequest,
    NotificationCreated,
    RecipeCollectedRequest,
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
    ) -> BatchNotificationResponse:
        """Send notifications when a user gains a new follower.

        Args:
            request: New follower request with recipient_ids and follower_id.

        Returns:
            BatchNotificationResponse with created notifications.

        Raises:
            UserNotFoundError: If follower or recipient user does not exist.
            PermissionDenied: If user lacks admin scope or relationship
                does not exist.
        """
        authenticated_user = require_current_user()

        logger.info(
            "Processing new follower notifications",
            follower_id=str(request.follower_id),
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
        )

        has_admin_scope = authenticated_user.has_scope("notification:admin")

        if not has_admin_scope:
            logger.warning(
                "User lacks notification:admin scope for new follower",
                user_id=authenticated_user.user_id,
            )
            raise PermissionDenied(detail="Requires notification:admin scope")

        try:
            follower = user_client.get_user(str(request.follower_id))
        except UserNotFoundError:
            logger.warning(
                "Follower user not found",
                follower_id=str(request.follower_id),
            )
            raise

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

        recipe_count = recipe_management_service_client.get_user_recipe_count(
            str(request.follower_id)
        )

        profile_url = f"{FRONTEND_BASE_URL}/users/{follower.username}"
        recipes_url = f"{FRONTEND_BASE_URL}/users/{follower.username}/recipes"

        created_notifications = []

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

            notification, _ = notification_service.create_notification(
                user=user,
                notification_category="NEW_FOLLOWER",
                notification_data={
                    "template_version": "1.0",
                    "recipient_name": recipient.full_name or recipient.username,
                    "follower_name": follower.full_name or follower.username,
                    "actor_name": follower.full_name or follower.username,
                    "follower_username": follower.username,
                    "follower_bio": follower.bio if hasattr(follower, "bio") else None,
                    "recipe_count": recipe_count,
                    "profile_url": profile_url,
                    "recipes_url": recipes_url,
                    "follower_id": str(request.follower_id),
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

    def send_mention_notifications(
        self,
        request: MentionRequest,
    ) -> BatchNotificationResponse:
        """Send notifications when users are mentioned in comments.

        Args:
            request: Mention request with recipient_ids and comment_id.

        Returns:
            BatchNotificationResponse with created notifications.

        Raises:
            CommentNotFoundError: If comment does not exist.
            RecipeNotFoundError: If recipe associated with comment does not exist.
            UserNotFoundError: If commenter or recipient user does not exist.
            PermissionDenied: If user lacks admin scope.
        """
        authenticated_user = require_current_user()

        logger.info(
            "Processing mention notifications",
            comment_id=str(request.comment_id),
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
        )

        has_admin_scope = authenticated_user.has_scope("notification:admin")

        if not has_admin_scope:
            logger.warning(
                "User lacks notification:admin scope for mention",
                user_id=authenticated_user.user_id,
            )
            raise PermissionDenied(detail="Requires notification:admin scope")

        try:
            comment = recipe_management_service_client.get_comment(request.comment_id)
        except CommentNotFoundError:
            logger.warning(
                "Comment not found",
                comment_id=str(request.comment_id),
            )
            raise

        try:
            commenter = user_client.get_user(str(comment.user_id))
        except UserNotFoundError:
            logger.warning(
                "Commenter user not found",
                user_id=str(comment.user_id),
            )
            raise

        try:
            recipe = recipe_management_service_client.get_recipe(comment.recipe_id)
        except RecipeNotFoundError:
            logger.warning(
                "Recipe not found",
                recipe_id=comment.recipe_id,
            )
            raise

        comment_preview = comment.comment_text
        if len(comment_preview) > 150:
            comment_preview = comment_preview[:150] + "..."

        recipe_url = f"{FRONTEND_BASE_URL}/recipes/{comment.recipe_id}"
        comment_url = (
            f"{FRONTEND_BASE_URL}/recipes/{comment.recipe_id}"
            f"#comment-{request.comment_id}"
        )

        created_notifications = []

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

            notification, _ = notification_service.create_notification(
                user=user,
                notification_category="MENTION",
                notification_data={
                    "template_version": "1.0",
                    "recipient_name": recipient.full_name or recipient.username,
                    "commenter_name": commenter.full_name or commenter.username,
                    "actor_name": commenter.full_name or commenter.username,
                    "commenter_username": commenter.username,
                    "comment_preview": comment_preview,
                    "recipe_name": recipe.title,
                    "recipe_url": recipe_url,
                    "comment_url": comment_url,
                    "comment_id": str(request.comment_id),
                    "recipient_id": str(recipient_id),
                    "commenter_id": str(comment.user_id),
                    "recipe_id": str(comment.recipe_id),
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
                "Mention notification created and queued",
                notification_id=str(notification.notification_id),
                recipient_id=str(recipient_id),
            )

        logger.info(
            "All mention notifications created",
            queued_count=len(created_notifications),
        )

        return BatchNotificationResponse(
            notifications=created_notifications,
            queued_count=len(created_notifications),
            message="Notifications queued successfully",
        )

    def _resolve_collector_identity(
        self,
        collector_id: UUID,
        recipe_author_id: UUID,
        authenticated_user: OAuth2User,
    ) -> tuple[str | None, str | None, bool]:
        """Resolve collector identity based on privacy rules.

        Args:
            collector_id: ID of the collector.
            recipe_author_id: ID of the recipe author.
            authenticated_user: Authenticated user making the request.

        Returns:
            Tuple of (collector_name, collector_username, is_anonymous).
        """
        has_admin_scope = authenticated_user.has_scope("notification:admin")

        if has_admin_scope:
            logger.info(
                "Admin scope detected, revealing collector identity",
                user_id=authenticated_user.user_id,
            )
            collector = user_client.get_user(str(collector_id))
            return (
                collector.full_name or collector.username,
                collector.username,
                False,
            )

        logger.info(
            "Validating follower relationship for user scope",
            user_id=authenticated_user.user_id,
            collector_id=str(collector_id),
            author_id=str(recipe_author_id),
        )

        is_follower = user_client.validate_follower_relationship(
            follower_id=str(collector_id),
            followee_id=str(recipe_author_id),
        )

        if is_follower:
            collector = user_client.get_user(str(collector_id))
            logger.info(
                "Collector follows author, revealing identity",
                collector_id=str(collector_id),
                author_id=str(recipe_author_id),
            )
            return (
                collector.full_name or collector.username,
                collector.username,
                False,
            )

        logger.info(
            "Collector does not follow author, sending anonymous notification",
            collector_id=str(collector_id),
            author_id=str(recipe_author_id),
        )
        return (None, None, True)

    def send_recipe_collected_notifications(
        self,
        request: RecipeCollectedRequest,
    ) -> BatchNotificationResponse:
        """Send notifications when a recipe is added to a collection.

        Privacy-aware: collector identity is only revealed if they
        follow the recipe author (or admin scope is used).

        Args:
            request: Recipe collected request with recipient_ids, recipe_id,
                collector_id, and collection_id.

        Returns:
            BatchNotificationResponse with created notifications.

        Raises:
            RecipeNotFoundError: If recipe does not exist.
            CollectionNotFoundError: If collection does not exist.
            UserNotFoundError: If collector or recipient does not exist.
        """
        authenticated_user = require_current_user()

        logger.info(
            "Processing recipe collected notifications",
            recipe_id=str(request.recipe_id),
            collection_id=str(request.collection_id),
            collector_id=str(request.collector_id),
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
        )

        try:
            recipe = recipe_management_service_client.get_recipe(request.recipe_id)
        except RecipeNotFoundError:
            logger.warning("Recipe not found", recipe_id=str(request.recipe_id))
            raise

        try:
            collection = recipe_management_service_client.get_collection(
                request.collection_id
            )
        except CollectionNotFoundError:
            logger.warning(
                "Collection not found",
                collection_id=str(request.collection_id),
            )
            raise

        collector_name, collector_username, is_anonymous = (
            self._resolve_collector_identity(
                request.collector_id,
                recipe.user_id,
                authenticated_user,
            )
        )

        recipe_url = f"{FRONTEND_BASE_URL}/recipes/{request.recipe_id}"
        collection_url = f"{FRONTEND_BASE_URL}/collections/{request.collection_id}"
        collector_profile_url = None
        if not is_anonymous and collector_username:
            collector_profile_url = f"{FRONTEND_BASE_URL}/users/{collector_username}"

        created_notifications = []

        for recipient_id in request.recipient_ids:
            recipient = user_client.get_user(str(recipient_id))
            user = User.objects.get(user_id=recipient_id)

            notification, _ = notification_service.create_notification(
                user=user,
                notification_category="RECIPE_COLLECTED",
                notification_data={
                    "template_version": "1.0",
                    "recipient_name": recipient.full_name or recipient.username,
                    "recipe_title": recipe.title,
                    "recipe_url": recipe_url,
                    "collection_name": collection.name,
                    "collection_description": collection.description,
                    "collection_url": collection_url,
                    "collector_name": collector_name,
                    "actor_name": collector_name or "Someone",
                    "collector_profile_url": collector_profile_url,
                    "is_anonymous": is_anonymous,
                    "recipe_id": str(request.recipe_id),
                    "collection_id": str(request.collection_id),
                    "collector_id": str(request.collector_id),
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
                "Notification created and queued",
                notification_id=str(notification.notification_id),
                recipient_id=str(recipient_id),
                is_anonymous=is_anonymous,
            )

        logger.info(
            "All recipe collected notifications created",
            queued_count=len(created_notifications),
        )

        return BatchNotificationResponse(
            notifications=created_notifications,
            queued_count=len(created_notifications),
            message="Notifications queued successfully",
        )


social_notification_service = SocialNotificationService()
