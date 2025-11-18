"""Service for handling recipe-related notifications."""

from django.db.models import Avg
from django.template.loader import render_to_string

import structlog
from rest_framework.exceptions import PermissionDenied

from core.auth.context import require_current_user
from core.config.downstream_urls import FRONTEND_BASE_URL
from core.exceptions import CommentNotFoundError, RecipeNotFoundError
from core.models import Review
from core.schemas.notification import (
    BatchNotificationResponse,
    NotificationCreated,
    RecipeCommentedRequest,
    RecipeFeaturedRequest,
    RecipeLikedRequest,
    RecipePublishedRequest,
    RecipeRatedRequest,
    RecipeSharedRequest,
    RecipeTrendingRequest,
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
            request: Recipe published request with recipient_ids and recipe_id

        Returns:
            BatchNotificationResponse with created notifications

        Raises:
            RecipeNotFoundError: If recipe does not exist
            PermissionDenied: If user lacks permission to notify recipients
        """
        # Get authenticated user from security context
        authenticated_user = require_current_user()

        logger.info(
            "Processing recipe published notifications",
            recipe_id=str(request.recipe_id),
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
        )

        # Fetch recipe details from recipe-management service
        try:
            recipe = recipe_management_service_client.get_recipe(request.recipe_id)
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
    ) -> BatchNotificationResponse:
        """Send notifications when a recipe is liked.

        Args:
            request: Recipe liked request with recipient_ids, recipe_id,
                and liker_id

        Returns:
            BatchNotificationResponse with created notifications

        Raises:
            RecipeNotFoundError: If recipe does not exist
            PermissionDenied: If user lacks permission to notify recipients
        """
        # Get authenticated user from security context
        authenticated_user = require_current_user()

        logger.info(
            "Processing recipe liked notifications",
            recipe_id=str(request.recipe_id),
            liker_id=str(request.liker_id),
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
        )

        # Fetch recipe details from recipe-management service
        try:
            recipe = recipe_management_service_client.get_recipe(request.recipe_id)
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
    ) -> BatchNotificationResponse:
        """Send notifications when a recipe is commented on.

        Args:
            request: Recipe commented request with recipient_ids and comment_id

        Returns:
            BatchNotificationResponse with created notifications

        Raises:
            CommentNotFoundError: If comment does not exist
            RecipeNotFoundError: If recipe does not exist
            PermissionDenied: If user lacks permission to notify recipients
        """
        # Get authenticated user from security context
        authenticated_user = require_current_user()

        logger.info(
            "Processing recipe commented notifications",
            comment_id=str(request.comment_id),
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
        )

        # Fetch comment details from recipe-management service
        try:
            comment = recipe_management_service_client.get_comment(request.comment_id)
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

    def send_recipe_shared_notifications(
        self,
        request: RecipeSharedRequest,
    ) -> BatchNotificationResponse:
        """Send notifications when a recipe is shared.

        Privacy-aware sharing: sharer identity is only revealed if they
        follow the recipe author (or admin scope is used).

        Args:
            request: Recipe shared request with recipient_ids, recipe_id,
                optional sharer_id, and optional share_message

        Returns:
            BatchNotificationResponse with created notifications

        Raises:
            RecipeNotFoundError: If recipe does not exist
            PermissionDenied: If user lacks permission to notify recipients
        """
        # Get authenticated user from security context
        authenticated_user = require_current_user()

        logger.info(
            "Processing recipe shared notifications",
            recipe_id=str(request.recipe_id),
            sharer_id=str(request.sharer_id) if request.sharer_id else None,
            recipient_count=len(request.recipient_ids),
            user_id=authenticated_user.user_id,
        )

        # Fetch recipe details from recipe-management service
        try:
            recipe = recipe_management_service_client.get_recipe(request.recipe_id)
        except RecipeNotFoundError:
            logger.warning(
                "Recipe not found",
                recipe_id=str(request.recipe_id),
            )
            raise

        # Determine if sharer identity should be revealed
        sharer_name = None
        is_anonymous = True

        if request.sharer_id is not None:
            has_admin_scope = authenticated_user.has_scope("notification:admin")

            if has_admin_scope:
                # Admin scope: always reveal sharer identity
                logger.info(
                    "Admin scope detected, revealing sharer identity",
                    user_id=authenticated_user.user_id,
                )
                sharer = user_client.get_user(str(request.sharer_id))
                sharer_name = sharer.full_name or sharer.username
                is_anonymous = False
            else:
                # User scope: check if sharer follows recipe author
                logger.info(
                    "Validating follower relationship for user scope",
                    user_id=authenticated_user.user_id,
                    sharer_id=str(request.sharer_id),
                    author_id=str(recipe.user_id),
                )

                author_id = str(recipe.user_id)
                sharer_id = str(request.sharer_id)

                is_follower = user_client.validate_follower_relationship(
                    follower_id=sharer_id,
                    followee_id=author_id,
                )

                if is_follower:
                    # Sharer follows author: reveal identity
                    sharer = user_client.get_user(str(request.sharer_id))
                    sharer_name = sharer.full_name or sharer.username
                    is_anonymous = False
                    logger.info(
                        "Sharer follows author, revealing identity",
                        sharer_id=sharer_id,
                        author_id=author_id,
                    )
                else:
                    # Sharer does not follow author: anonymous share
                    logger.info(
                        "Sharer does not follow author, sending anonymous notification",
                        sharer_id=sharer_id,
                        author_id=author_id,
                    )

        # Construct recipe URL
        recipe_url = f"{FRONTEND_BASE_URL}/recipes/{request.recipe_id}"

        # Create notifications for each recipient
        created_notifications = []

        for recipient_id in request.recipient_ids:
            # Fetch recipient details
            recipient = user_client.get_user(str(recipient_id))

            # Prepare notification subject and message
            if is_anonymous:
                subject = f"Someone shared a recipe with you: {recipe.title}"
            else:
                subject = f"{sharer_name} shared a recipe with you: {recipe.title}"

            message = render_to_string(
                "emails/recipe_shared.html",
                {
                    "recipient_name": (recipient.full_name or recipient.username),
                    "recipe_title": recipe.title,
                    "recipe_url": recipe_url,
                    "sharer_name": sharer_name,
                    "share_message": request.share_message,
                    "is_anonymous": is_anonymous,
                },
            )

            # Create notification with metadata
            notification = notification_service.create_notification(
                recipient_email=recipient.email,
                subject=subject,
                message=message,
                notification_type="email",
                metadata={
                    "template_type": "recipe_shared",
                    "recipe_id": str(request.recipe_id),
                    "sharer_id": str(request.sharer_id) if request.sharer_id else None,
                    "recipient_id": str(recipient_id),
                    "is_anonymous": is_anonymous,
                    "share_message": request.share_message,
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
                is_anonymous=is_anonymous,
            )

        logger.info(
            "All recipe shared notifications created",
            queued_count=len(created_notifications),
        )

        return BatchNotificationResponse(
            notifications=created_notifications,
            queued_count=len(created_notifications),
            message="Notifications queued successfully",
        )

    def _get_rating_data(self, recipe_id: int, rater_id) -> tuple[float, float, int]:
        """Get rating data from database.

        Args:
            recipe_id: ID of the recipe
            rater_id: ID of the user who rated

        Returns:
            Tuple of (individual_rating, average_rating, total_reviews)

        Raises:
            ValueError: If rating not found
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
                and rater_id

        Returns:
            BatchNotificationResponse with created notifications

        Raises:
            RecipeNotFoundError: If recipe does not exist
            UserNotFoundError: If rater or recipient does not exist
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

        # Determine if rater identity should be revealed
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

        # Construct URLs
        recipe_url = f"{FRONTEND_BASE_URL}/recipes/{request.recipe_id}"
        rater_profile_url = None
        if not is_anonymous and rater_username:
            rater_profile_url = f"{FRONTEND_BASE_URL}/users/{rater_username}"

        # Create notifications for each recipient
        created_notifications = []

        for recipient_id in request.recipient_ids:
            recipient = user_client.get_user(str(recipient_id))

            if is_anonymous:
                subject = (
                    f"Someone rated your recipe: {recipe.title} "
                    f"({individual_rating} stars)"
                )
            else:
                subject = (
                    f"{rater_name} rated your recipe: {recipe.title} "
                    f"({individual_rating} stars)"
                )

            message = render_to_string(
                "emails/recipe_rated.html",
                {
                    "recipient_name": (recipient.full_name or recipient.username),
                    "recipe_title": recipe.title,
                    "recipe_url": recipe_url,
                    "rater_name": rater_name,
                    "rater_profile_url": rater_profile_url,
                    "is_anonymous": is_anonymous,
                    "individual_rating": individual_rating,
                    "average_rating": average_rating,
                    "total_reviews": total_reviews,
                },
            )

            notification = notification_service.create_notification(
                recipient_email=recipient.email,
                subject=subject,
                message=message,
                notification_type="email",
                metadata={
                    "template_type": "recipe_rated",
                    "recipe_id": str(request.recipe_id),
                    "rater_id": str(request.rater_id),
                    "recipient_id": str(recipient_id),
                    "is_anonymous": is_anonymous,
                    "rating_value": str(individual_rating),
                    "average_rating": str(average_rating),
                },
                auto_queue=True,
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
                and optional featured_reason

        Returns:
            BatchNotificationResponse with created notifications

        Raises:
            RecipeNotFoundError: If recipe does not exist
            UserNotFoundError: If recipient does not exist
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

            if request.featured_reason:
                subject = (
                    f"Your recipe is featured: {recipe.title} "
                    f"({request.featured_reason})"
                )
            else:
                subject = f"Your recipe is featured: {recipe.title}"

            message = render_to_string(
                "emails/recipe_featured.html",
                {
                    "recipient_name": (recipient.full_name or recipient.username),
                    "recipe_title": recipe.title,
                    "recipe_url": recipe_url,
                    "featured_reason": request.featured_reason,
                },
            )

            notification = notification_service.create_notification(
                recipient_email=recipient.email,
                subject=subject,
                message=message,
                notification_type="email",
                metadata={
                    "template_type": "recipe_featured",
                    "recipe_id": str(request.recipe_id),
                    "featured_reason": request.featured_reason,
                    "recipient_id": str(recipient_id),
                },
                auto_queue=True,
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
                and optional trending_metrics

        Returns:
            BatchNotificationResponse with created notifications

        Raises:
            RecipeNotFoundError: If recipe does not exist
            UserNotFoundError: If recipient does not exist
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

            subject = f"Your recipe is trending: {recipe.title}"

            message = render_to_string(
                "emails/recipe_trending.html",
                {
                    "recipient_name": (recipient.full_name or recipient.username),
                    "recipe_title": recipe.title,
                    "recipe_url": recipe_url,
                    "trending_metrics": request.trending_metrics,
                },
            )

            notification = notification_service.create_notification(
                recipient_email=recipient.email,
                subject=subject,
                message=message,
                notification_type="email",
                metadata={
                    "template_type": "recipe_trending",
                    "recipe_id": str(request.recipe_id),
                    "trending_metrics": request.trending_metrics,
                    "recipient_id": str(recipient_id),
                },
                auto_queue=True,
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


# Global service instance
recipe_notification_service = RecipeNotificationService()
