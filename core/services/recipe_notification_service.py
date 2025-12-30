"""Service for handling recipe-related notifications."""

from django.db.models import Avg

import structlog
from rest_framework.exceptions import PermissionDenied

from core.auth.context import require_current_user
from core.config.downstream_urls import FRONTEND_BASE_URL
from core.exceptions import CommentNotFoundError, RecipeNotFoundError
from core.models import Review, User
from core.schemas.notification import (
    BatchNotificationResponse,
    NotificationCreated,
    RecipeCommentedRequest,
    RecipeFeaturedRequest,
    RecipeLikedRequest,
    RecipePublishedRequest,
    RecipeRatedRequest,
    RecipeTrendingRequest,
    ShareRecipeRequest,
)
from core.services.downstream.media_management_service_client import (
    media_management_service_client,
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
    ) -> BatchNotificationResponse:
        """Send notifications when a recipe is published.

        Args:
            request: Recipe published request with recipient_ids and recipe_id.

        Returns:
            BatchNotificationResponse with created notifications.

        Raises:
            RecipeNotFoundError: If recipe does not exist.
            PermissionDenied: If user lacks permission to notify recipients.
        """
        authenticated_user = require_current_user()

        logger.info(
            "Processing recipe published notifications",
            recipe_id=str(request.recipe_id),
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
        )

        try:
            recipe = recipe_management_service_client.get_recipe(request.recipe_id)
        except RecipeNotFoundError:
            logger.warning("Recipe not found", recipe_id=str(request.recipe_id))
            raise

        has_admin_scope = authenticated_user.has_scope("notification:admin")

        if not has_admin_scope:
            logger.info(
                "Validating follower relationships for user scope",
                user_id=authenticated_user.user_id,
                author_id=recipe.user_id,
            )

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
                    detail="One or more recipients are not followers of the author"
                )

        author = user_client.get_user(str(recipe.user_id))
        recipe_url = f"{FRONTEND_BASE_URL}/recipes/{request.recipe_id}"

        created_notifications = []

        for recipient_id in request.recipient_ids:
            recipient = user_client.get_user(str(recipient_id))
            user = User.objects.get(user_id=recipient_id)

            notification, _ = notification_service.create_notification(
                user=user,
                notification_category="RECIPE_PUBLISHED",
                notification_data={
                    "template_version": "1.0",
                    "recipient_name": recipient.full_name or recipient.username,
                    "author_name": author.full_name or author.username,
                    "actor_name": author.full_name or author.username,
                    "recipe_title": recipe.title,
                    "recipe_url": recipe_url,
                    "recipe_id": str(request.recipe_id),
                    "author_id": str(recipe.user_id),
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
    ) -> BatchNotificationResponse:
        """Send notifications when a recipe is liked.

        Args:
            request: Recipe liked request with recipient_ids, recipe_id,
                and liker_id.

        Returns:
            BatchNotificationResponse with created notifications.

        Raises:
            RecipeNotFoundError: If recipe does not exist.
            PermissionDenied: If user lacks permission to notify recipients.
        """
        authenticated_user = require_current_user()

        logger.info(
            "Processing recipe liked notifications",
            recipe_id=str(request.recipe_id),
            liker_id=str(request.liker_id),
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
        )

        try:
            recipe = recipe_management_service_client.get_recipe(request.recipe_id)
        except RecipeNotFoundError:
            logger.warning("Recipe not found", recipe_id=str(request.recipe_id))
            raise

        has_admin_scope = authenticated_user.has_scope("notification:admin")

        if not has_admin_scope:
            logger.info(
                "Validating follower relationship for user scope",
                user_id=authenticated_user.user_id,
                liker_id=str(request.liker_id),
                author_id=str(recipe.user_id),
            )

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

        liker = user_client.get_user(str(request.liker_id))
        recipe_url = f"{FRONTEND_BASE_URL}/recipes/{request.recipe_id}"

        created_notifications = []

        for recipient_id in request.recipient_ids:
            recipient = user_client.get_user(str(recipient_id))
            user = User.objects.get(user_id=recipient_id)

            notification, _ = notification_service.create_notification(
                user=user,
                notification_category="RECIPE_LIKED",
                notification_data={
                    "template_version": "1.0",
                    "recipient_name": recipient.full_name or recipient.username,
                    "liker_name": liker.full_name or liker.username,
                    "actor_name": liker.full_name or liker.username,
                    "recipe_title": recipe.title,
                    "recipe_url": recipe_url,
                    "recipe_id": str(request.recipe_id),
                    "liker_id": str(request.liker_id),
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
    ) -> BatchNotificationResponse:
        """Send notifications when a recipe is commented on.

        Args:
            request: Recipe commented request with recipient_ids and comment_id.

        Returns:
            BatchNotificationResponse with created notifications.

        Raises:
            CommentNotFoundError: If comment does not exist.
            RecipeNotFoundError: If recipe does not exist.
            PermissionDenied: If user lacks permission to notify recipients.
        """
        authenticated_user = require_current_user()

        logger.info(
            "Processing recipe commented notifications",
            comment_id=str(request.comment_id),
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
        )

        try:
            comment = recipe_management_service_client.get_comment(request.comment_id)
        except CommentNotFoundError:
            logger.warning("Comment not found", comment_id=str(request.comment_id))
            raise

        try:
            recipe = recipe_management_service_client.get_recipe(comment.recipe_id)
        except RecipeNotFoundError:
            logger.warning("Recipe not found", recipe_id=comment.recipe_id)
            raise

        has_admin_scope = authenticated_user.has_scope("notification:admin")

        if not has_admin_scope:
            logger.info(
                "Validating follower relationship for user scope",
                user_id=authenticated_user.user_id,
                commenter_id=str(comment.user_id),
                author_id=str(recipe.user_id),
            )

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

        commenter = user_client.get_user(str(comment.user_id))
        recipe_url = f"{FRONTEND_BASE_URL}/recipes/{comment.recipe_id}"

        comment_preview = comment.comment_text
        if len(comment_preview) > 150:
            comment_preview = comment_preview[:150] + "..."

        created_notifications = []

        for recipient_id in request.recipient_ids:
            recipient = user_client.get_user(str(recipient_id))
            user = User.objects.get(user_id=recipient_id)

            notification, _ = notification_service.create_notification(
                user=user,
                notification_category="RECIPE_COMMENTED",
                notification_data={
                    "template_version": "1.0",
                    "recipient_name": recipient.full_name or recipient.username,
                    "commenter_name": commenter.full_name or commenter.username,
                    "actor_name": commenter.full_name or commenter.username,
                    "recipe_title": recipe.title,
                    "comment_preview": comment_preview,
                    "recipe_url": recipe_url,
                    "comment_id": str(request.comment_id),
                    "recipe_id": str(comment.recipe_id),
                    "commenter_id": str(comment.user_id),
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
            "All recipe commented notifications created",
            queued_count=len(created_notifications),
        )

        return BatchNotificationResponse(
            notifications=created_notifications,
            queued_count=len(created_notifications),
            message="Notifications queued successfully",
        )

    def share_recipe_with_users(
        self,
        request: ShareRecipeRequest,
    ) -> BatchNotificationResponse:
        """Share a recipe with users and send notifications.

        Sends two types of notifications:
        1. To recipients: Recipe preview with image, share message, sharer identity.
        2. To recipe author: Privacy-aware notification about the share.

        Args:
            request: Share recipe request with recipient_ids, recipe_id,
                optional sharer_id, and optional share_message.

        Returns:
            BatchNotificationResponse with created notifications.

        Raises:
            RecipeNotFoundError: If recipe does not exist.
            PermissionDenied: If user lacks permission to notify recipients.
        """
        authenticated_user = require_current_user()

        logger.info(
            "Processing share recipe request",
            recipe_id=str(request.recipe_id),
            sharer_id=str(request.sharer_id) if request.sharer_id else None,
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
        )

        try:
            recipe = recipe_management_service_client.get_recipe(request.recipe_id)
        except RecipeNotFoundError:
            logger.warning("Recipe not found", recipe_id=str(request.recipe_id))
            raise

        media_ids = media_management_service_client.get_recipe_media_ids(
            request.recipe_id
        )
        recipe_image_url = None
        if media_ids:
            recipe_image_url = (
                media_management_service_client.construct_media_download_url(
                    media_ids[0]
                )
            )
            logger.info(
                "Recipe image found",
                recipe_id=request.recipe_id,
                media_id=media_ids[0],
                media_count=len(media_ids),
            )

        recipe_url = f"{FRONTEND_BASE_URL}/recipes/{request.recipe_id}"

        sharer_name = None
        if request.sharer_id is not None:
            sharer = user_client.get_user(str(request.sharer_id))
            sharer_name = sharer.full_name or sharer.username

        created_notifications = []

        for recipient_id in request.recipient_ids:
            recipient = user_client.get_user(str(recipient_id))
            user = User.objects.get(user_id=recipient_id)

            notification, _ = notification_service.create_notification(
                user=user,
                notification_category="RECIPE_SHARED",
                notification_data={
                    "template_version": "1.0",
                    "recipient_name": recipient.full_name or recipient.username,
                    "recipe_title": recipe.title,
                    "recipe_description": recipe.description,
                    "recipe_url": recipe_url,
                    "recipe_image_url": recipe_image_url,
                    "sharer_name": sharer_name,
                    "actor_name": sharer_name or "Someone",
                    "share_message": request.share_message,
                    "is_anonymous": sharer_name is None,
                    "recipe_id": str(request.recipe_id),
                    "sharer_id": str(request.sharer_id) if request.sharer_id else None,
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
                "Recipient notification created and queued",
                notification_id=str(notification.notification_id),
                recipient_id=str(recipient_id),
            )

        author_id = recipe.user_id
        author_sharer_name, author_is_anonymous = self._determine_author_privacy(
            request.sharer_id, author_id, sharer_name, authenticated_user
        )
        author = user_client.get_user(str(author_id))
        author_user = User.objects.get(user_id=author_id)

        recipient_count = len(request.recipient_ids)

        notification, _ = notification_service.create_notification(
            user=author_user,
            notification_category="RECIPE_SHARED",
            notification_data={
                "template_version": "1.0",
                "author_name": author.full_name or author.username,
                "recipient_name": author.full_name or author.username,
                "recipe_title": recipe.title,
                "recipe_url": recipe_url,
                "sharer_name": author_sharer_name,
                "actor_name": author_sharer_name or "Someone",
                "recipient_count": recipient_count,
                "share_message": request.share_message,
                "is_anonymous": author_is_anonymous,
                "recipe_id": str(request.recipe_id),
                "sharer_id": str(request.sharer_id) if request.sharer_id else None,
                "recipient_id": str(author_id),
            },
            recipient_email=author.email,
        )

        created_notifications.append(
            NotificationCreated(
                notification_id=notification.notification_id,
                recipient_id=author_id,
            )
        )

        logger.info(
            "Author notification created and queued",
            notification_id=str(notification.notification_id),
            author_id=str(author_id),
            is_anonymous=author_is_anonymous,
        )

        logger.info(
            "All share recipe notifications created",
            queued_count=len(created_notifications),
            recipient_notifications=len(request.recipient_ids),
            author_notification=1,
        )

        return BatchNotificationResponse(
            notifications=created_notifications,
            queued_count=len(created_notifications),
            message="Notifications queued successfully",
        )

    def _determine_author_privacy(
        self, sharer_id, author_id, sharer_name, authenticated_user
    ) -> tuple[str | None, bool]:
        """Determine privacy settings for author notification.

        Returns:
            Tuple of (author_sharer_name, author_is_anonymous).
        """
        if sharer_id is None:
            return None, True

        has_admin_scope = authenticated_user.has_scope("notification:admin")

        if has_admin_scope:
            logger.info(
                "Admin scope detected, revealing sharer identity to author",
                user_id=authenticated_user.user_id,
            )
            return sharer_name, False

        is_follower = user_client.validate_follower_relationship(
            follower_id=str(sharer_id),
            followee_id=str(author_id),
        )

        if is_follower:
            logger.info(
                "Sharer follows author, revealing identity",
                sharer_id=str(sharer_id),
                author_id=str(author_id),
            )
            return sharer_name, False

        logger.info(
            "Sharer does not follow author, sending anonymous notification",
            sharer_id=str(sharer_id),
            author_id=str(author_id),
        )
        return None, True

    def _get_rating_data(self, recipe_id: int, rater_id) -> tuple[float, float, int]:
        """Get rating data from database.

        Args:
            recipe_id: ID of the recipe.
            rater_id: ID of the user who rated.

        Returns:
            Tuple of (individual_rating, average_rating, total_reviews).

        Raises:
            ValueError: If rating not found.
        """
        try:
            review = Review.objects.get(
                recipe_id=recipe_id,
                user_id=rater_id,
            )
            individual_rating = float(review.rating)
        except Review.DoesNotExist as e:
            logger.error(
                "Review not found for rater and recipe",
                recipe_id=recipe_id,
                rater_id=str(rater_id),
            )
            raise ValueError(
                f"No rating found for recipe {recipe_id} by user {rater_id}"
            ) from e

        rating_stats = Review.objects.filter(recipe_id=recipe_id).aggregate(
            average=Avg("rating"),
        )
        average_rating = (
            float(rating_stats["average"]) if rating_stats["average"] else 0.0
        )
        total_reviews = Review.objects.filter(recipe_id=recipe_id).count()

        return individual_rating, average_rating, total_reviews

    def send_recipe_rated_notifications(
        self,
        request: RecipeRatedRequest,
    ) -> BatchNotificationResponse:
        """Send notifications when a recipe is rated.

        Privacy-aware: rater identity is only revealed if they
        follow the recipe author (or admin scope is used).

        Args:
            request: Recipe rated request with recipient_ids, recipe_id,
                and rater_id.

        Returns:
            BatchNotificationResponse with created notifications.

        Raises:
            RecipeNotFoundError: If recipe does not exist.
            UserNotFoundError: If rater or recipient does not exist.
        """
        authenticated_user = require_current_user()

        logger.info(
            "Processing recipe rated notifications",
            recipe_id=str(request.recipe_id),
            rater_id=str(request.rater_id),
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
        )

        try:
            recipe = recipe_management_service_client.get_recipe(request.recipe_id)
        except RecipeNotFoundError:
            logger.warning("Recipe not found", recipe_id=str(request.recipe_id))
            raise

        individual_rating, average_rating, total_reviews = self._get_rating_data(
            request.recipe_id, request.rater_id
        )

        rater_name = None
        rater_username = None
        is_anonymous = True

        has_admin_scope = authenticated_user.has_scope("notification:admin")

        if has_admin_scope:
            logger.info(
                "Admin scope detected, revealing rater identity",
                user_id=authenticated_user.user_id,
            )
            rater = user_client.get_user(str(request.rater_id))
            rater_name = rater.full_name or rater.username
            rater_username = rater.username
            is_anonymous = False
        else:
            logger.info(
                "Validating follower relationship for user scope",
                user_id=authenticated_user.user_id,
                rater_id=str(request.rater_id),
                author_id=str(recipe.user_id),
            )

            is_follower = user_client.validate_follower_relationship(
                follower_id=str(request.rater_id),
                followee_id=str(recipe.user_id),
            )

            if is_follower:
                rater = user_client.get_user(str(request.rater_id))
                rater_name = rater.full_name or rater.username
                rater_username = rater.username
                is_anonymous = False
                logger.info(
                    "Rater follows author, revealing identity",
                    rater_id=str(request.rater_id),
                    author_id=str(recipe.user_id),
                )
            else:
                logger.info(
                    "Rater does not follow author, sending anonymous notification",
                    rater_id=str(request.rater_id),
                    author_id=str(recipe.user_id),
                )

        recipe_url = f"{FRONTEND_BASE_URL}/recipes/{request.recipe_id}"
        rater_profile_url = None
        if not is_anonymous and rater_username:
            rater_profile_url = f"{FRONTEND_BASE_URL}/users/{rater_username}"

        created_notifications = []

        for recipient_id in request.recipient_ids:
            recipient = user_client.get_user(str(recipient_id))
            user = User.objects.get(user_id=recipient_id)

            notification, _ = notification_service.create_notification(
                user=user,
                notification_category="RECIPE_RATED",
                notification_data={
                    "template_version": "1.0",
                    "recipient_name": recipient.full_name or recipient.username,
                    "recipe_title": recipe.title,
                    "recipe_url": recipe_url,
                    "rater_name": rater_name,
                    "actor_name": rater_name or "Someone",
                    "rater_profile_url": rater_profile_url,
                    "is_anonymous": is_anonymous,
                    "individual_rating": individual_rating,
                    "average_rating": average_rating,
                    "total_reviews": total_reviews,
                    "recipe_id": str(request.recipe_id),
                    "rater_id": str(request.rater_id),
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
            "All recipe rated notifications created",
            queued_count=len(created_notifications),
        )

        return BatchNotificationResponse(
            notifications=created_notifications,
            queued_count=len(created_notifications),
            message="Notifications queued successfully",
        )

    def send_recipe_featured_notifications(
        self,
        request: RecipeFeaturedRequest,
    ) -> BatchNotificationResponse:
        """Send notifications when a recipe is featured.

        Args:
            request: Recipe featured request with recipient_ids, recipe_id,
                and optional featured_reason.

        Returns:
            BatchNotificationResponse with created notifications.

        Raises:
            RecipeNotFoundError: If recipe does not exist.
            UserNotFoundError: If recipient does not exist.
        """
        authenticated_user = require_current_user()

        logger.info(
            "Processing recipe featured notifications",
            recipe_id=str(request.recipe_id),
            recipient_count=len(request.recipient_ids),
            featured_reason=request.featured_reason,
            user_id=authenticated_user.user_id,
        )

        try:
            recipe = recipe_management_service_client.get_recipe(request.recipe_id)
        except RecipeNotFoundError:
            logger.warning("Recipe not found", recipe_id=str(request.recipe_id))
            raise

        recipe_url = f"{FRONTEND_BASE_URL}/recipes/{request.recipe_id}"

        created_notifications = []

        for recipient_id in request.recipient_ids:
            recipient = user_client.get_user(str(recipient_id))
            user = User.objects.get(user_id=recipient_id)

            notification, _ = notification_service.create_notification(
                user=user,
                notification_category="RECIPE_FEATURED",
                notification_data={
                    "template_version": "1.0",
                    "recipient_name": recipient.full_name or recipient.username,
                    "recipe_title": recipe.title,
                    "recipe_url": recipe_url,
                    "featured_reason": request.featured_reason,
                    "recipe_id": str(request.recipe_id),
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
            "All recipe featured notifications created",
            queued_count=len(created_notifications),
        )

        return BatchNotificationResponse(
            notifications=created_notifications,
            queued_count=len(created_notifications),
            message="Notifications queued successfully",
        )

    def send_recipe_trending_notifications(
        self,
        request: RecipeTrendingRequest,
    ) -> BatchNotificationResponse:
        """Send notifications when a recipe is trending.

        Args:
            request: Recipe trending request with recipient_ids, recipe_id,
                and optional trending_metrics.

        Returns:
            BatchNotificationResponse with created notifications.

        Raises:
            RecipeNotFoundError: If recipe does not exist.
            UserNotFoundError: If recipient does not exist.
        """
        authenticated_user = require_current_user()

        logger.info(
            "Processing recipe trending notifications",
            recipe_id=str(request.recipe_id),
            recipient_count=len(request.recipient_ids),
            trending_metrics=request.trending_metrics,
            user_id=authenticated_user.user_id,
        )

        try:
            recipe = recipe_management_service_client.get_recipe(request.recipe_id)
        except RecipeNotFoundError:
            logger.warning("Recipe not found", recipe_id=str(request.recipe_id))
            raise

        recipe_url = f"{FRONTEND_BASE_URL}/recipes/{request.recipe_id}"

        created_notifications = []

        for recipient_id in request.recipient_ids:
            recipient = user_client.get_user(str(recipient_id))
            user = User.objects.get(user_id=recipient_id)

            notification, _ = notification_service.create_notification(
                user=user,
                notification_category="RECIPE_TRENDING",
                notification_data={
                    "template_version": "1.0",
                    "recipient_name": recipient.full_name or recipient.username,
                    "recipe_title": recipe.title,
                    "recipe_url": recipe_url,
                    "trending_metrics": request.trending_metrics,
                    "recipe_id": str(request.recipe_id),
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
            "All recipe trending notifications created",
            queued_count=len(created_notifications),
        )

        return BatchNotificationResponse(
            notifications=created_notifications,
            queued_count=len(created_notifications),
            message="Notifications queued successfully",
        )


recipe_notification_service = RecipeNotificationService()
