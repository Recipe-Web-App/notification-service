"""API views for core application."""

from datetime import datetime
from uuid import UUID

import structlog
from pydantic import ValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.auth.oauth2 import OAuth2Authentication
from core.pagination import NotificationPageNumberPagination
from core.schemas.notification import (
    EmailChangedRequest,
    MentionRequest,
    NewFollowerRequest,
    NotificationDetail,
    NotificationStats,
    PasswordResetRequest,
    RecipeCollectedRequest,
    RecipeCommentedRequest,
    RecipeFeaturedRequest,
    RecipeLikedRequest,
    RecipePublishedRequest,
    RecipeRatedRequest,
    RecipeSharedRequest,
    RecipeTrendingRequest,
    TemplateListResponse,
    WelcomeRequest,
)
from core.services import health_service
from core.services.admin_service import admin_service
from core.services.notification_service import notification_service
from core.services.recipe_notification_service import (
    recipe_notification_service,
)
from core.services.social_notification_service import (
    social_notification_service,
)
from core.services.system_notification_service import (
    system_notification_service,
)

logger = structlog.get_logger(__name__)


class LivenessCheckView(APIView):
    """Liveness probe endpoint for Kubernetes.

    Returns 200 if the service is alive and running.
    This should not check external dependencies.

    This endpoint is exempt from authentication to allow Kubernetes probes.
    """

    def __init__(self, **kwargs):
        """Initialize view with authentication exemptions.

        Exempt from authentication - health checks must be accessible without auth.

        Args:
            **kwargs: Keyword arguments passed to parent class
        """
        super().__init__(**kwargs)
        self.authentication_classes = []
        self.permission_classes = [AllowAny]

    def get(self, _request):
        """Handle GET request for liveness check.

        Args:
            _request: HTTP request object (unused).

        Returns:
            Response object with status OK if service is alive.
        """
        liveness = health_service.get_liveness_status()
        return Response(liveness.model_dump(), status=status.HTTP_200_OK)


class ReadinessCheckView(APIView):
    """Readiness probe endpoint for Kubernetes.

    Returns 200 if the service is ready to serve traffic.
    Returns degraded status (200 OK) when database is unavailable,
    allowing service to stay alive while background reconnection continues.

    This endpoint is exempt from authentication to allow Kubernetes probes.
    """

    def __init__(self, **kwargs):
        """Initialize view with authentication exemptions.

        Exempt from authentication - health checks must be accessible without auth.

        Args:
            **kwargs: Keyword arguments passed to parent class
        """
        super().__init__(**kwargs)
        self.authentication_classes = []
        self.permission_classes = [AllowAny]

    def get(self, _request):
        """Handle GET request for readiness check.

        Args:
            _request: HTTP request object (unused).

        Returns:
            Response object with status OK if service is ready or degraded.
        """
        readiness = health_service.get_readiness_status()
        return Response(readiness.model_dump(), status=status.HTTP_200_OK)


class RecipePublishedView(APIView):
    """API endpoint for sending recipe published notifications.

    Sends email notifications to followers when a recipe is published.
    Requires notification:user or notification:admin scope.
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """Handle POST request to send recipe published notifications.

        Args:
            request: HTTP request object containing recipient_ids and
                recipe_id

        Returns:
            202 Accepted with BatchNotificationResponse if successful
            400 Bad Request if validation fails
            401 Unauthorized if authentication fails
            403 Forbidden if user lacks required scope or permissions
            404 Not Found if recipe doesn't exist
            429 Too Many Requests if rate limit exceeded
            500 Internal Server Error for unexpected errors
        """
        logger.info(
            "Recipe published notification request received",
            user_id=request.user.user_id if request.user else None,
        )

        # Check user has required scope
        if not request.user.has_scope(
            "notification:user"
        ) and not request.user.has_scope("notification:admin"):
            logger.warning(
                "User lacks required scope for recipe notifications",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": ("You do not have permission to perform this action"),
                    "detail": (
                        "Requires notification:user or notification:admin scope"
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate request body with Pydantic
        try:
            recipe_published_request = RecipePublishedRequest(**request.data)
        except ValidationError as e:
            logger.warning(
                "Invalid request body for recipe published notification",
                validation_errors=e.errors(),
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid request parameters",
                    "errors": e.errors(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call service to send notifications
        try:
            response_data = (
                recipe_notification_service.send_recipe_published_notifications(
                    request=recipe_published_request,
                )
            )

            logger.info(
                "Recipe published notifications queued successfully",
                queued_count=response_data.queued_count,
            )

            return Response(
                response_data.model_dump(),
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception:
            # Let DRF exception handler handle it
            # (RecipeNotFoundError, PermissionDenied, etc.)
            raise


class RecipeLikedView(APIView):
    """API endpoint for sending recipe liked notifications.

    Sends email notification to recipe author when someone likes their recipe.
    Requires notification:user or notification:admin scope.
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """Handle POST request to send recipe liked notifications.

        Args:
            request: HTTP request object containing recipient_ids,
                recipe_id, and liker_id

        Returns:
            202 Accepted with BatchNotificationResponse if successful
            400 Bad Request if validation fails
            401 Unauthorized if authentication fails
            403 Forbidden if user lacks required scope or permissions
            404 Not Found if recipe or liker doesn't exist
            429 Too Many Requests if rate limit exceeded
            500 Internal Server Error for unexpected errors
        """
        logger.info(
            "Recipe liked notification request received",
            user_id=request.user.user_id if request.user else None,
        )

        # Check user has required scope
        if not request.user.has_scope(
            "notification:user"
        ) and not request.user.has_scope("notification:admin"):
            logger.warning(
                "User lacks required scope for recipe notifications",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": ("You do not have permission to perform this action"),
                    "detail": (
                        "Requires notification:user or notification:admin scope"
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate request body with Pydantic
        try:
            recipe_liked_request = RecipeLikedRequest(**request.data)
        except ValidationError as e:
            logger.warning(
                "Invalid request body for recipe liked notification",
                validation_errors=e.errors(),
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid request parameters",
                    "errors": e.errors(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call service to send notifications
        try:
            response_data = recipe_notification_service.send_recipe_liked_notifications(
                request=recipe_liked_request,
            )

            logger.info(
                "Recipe liked notifications queued successfully",
                queued_count=response_data.queued_count,
            )

            return Response(
                response_data.model_dump(),
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception:
            # Let DRF exception handler handle it
            # (RecipeNotFoundError, PermissionDenied, etc.)
            raise


class RecipeCommentedView(APIView):
    """API endpoint for sending recipe commented notifications.

    Sends email notification to recipe author when someone comments on their recipe.
    Requires notification:user or notification:admin scope.
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """Handle POST request to send recipe commented notifications.

        Args:
            request: HTTP request object containing recipient_ids and comment_id

        Returns:
            202 Accepted with BatchNotificationResponse if successful
            400 Bad Request if validation fails
            401 Unauthorized if authentication fails
            403 Forbidden if user lacks required scope or permissions
            404 Not Found if comment or recipe doesn't exist
            429 Too Many Requests if rate limit exceeded
            500 Internal Server Error for unexpected errors
        """
        logger.info(
            "Recipe commented notification request received",
            user_id=request.user.user_id if request.user else None,
        )

        # Check user has required scope
        if not request.user.has_scope(
            "notification:user"
        ) and not request.user.has_scope("notification:admin"):
            logger.warning(
                "User lacks required scope for recipe notifications",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": ("You do not have permission to perform this action"),
                    "detail": (
                        "Requires notification:user or notification:admin scope"
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate request body with Pydantic
        try:
            recipe_commented_request = RecipeCommentedRequest(**request.data)
        except ValidationError as e:
            logger.warning(
                "Invalid request body for recipe commented notification",
                validation_errors=e.errors(),
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid request parameters",
                    "errors": e.errors(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call service to send notifications
        try:
            response_data = (
                recipe_notification_service.send_recipe_commented_notifications(
                    request=recipe_commented_request,
                )
            )

            logger.info(
                "Recipe commented notifications queued successfully",
                queued_count=response_data.queued_count,
            )

            return Response(
                response_data.model_dump(),
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception:
            # Let DRF exception handler handle it
            # (CommentNotFoundError, RecipeNotFoundError, PermissionDenied, etc.)
            raise


class RecipeSharedView(APIView):
    """API endpoint for sending recipe shared notifications.

    Sends email notification to recipients when a recipe is shared.
    Privacy-aware: sharer identity revealed only if they follow recipe author.
    Requires notification:user or notification:admin scope.
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """Handle POST request to send recipe shared notifications.

        Args:
            request: HTTP request object containing recipient_ids,
                recipe_id, optional sharer_id, and optional share_message

        Returns:
            202 Accepted with BatchNotificationResponse if successful
            400 Bad Request if validation fails
            401 Unauthorized if authentication fails
            403 Forbidden if user lacks required scope or permissions
            404 Not Found if recipe or sharer doesn't exist
            429 Too Many Requests if rate limit exceeded
            500 Internal Server Error for unexpected errors
        """
        logger.info(
            "Recipe shared notification request received",
            user_id=request.user.user_id if request.user else None,
        )

        # Check user has required scope
        if not request.user.has_scope(
            "notification:user"
        ) and not request.user.has_scope("notification:admin"):
            logger.warning(
                "User lacks required scope for recipe notifications",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": ("You do not have permission to perform this action"),
                    "detail": (
                        "Requires notification:user or notification:admin scope"
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate request body with Pydantic
        try:
            recipe_shared_request = RecipeSharedRequest(**request.data)
        except ValidationError as e:
            logger.warning(
                "Invalid request body for recipe shared notification",
                validation_errors=e.errors(),
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid request parameters",
                    "errors": e.errors(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call service to send notifications
        try:
            response_data = (
                recipe_notification_service.send_recipe_shared_notifications(
                    request=recipe_shared_request,
                )
            )

            logger.info(
                "Recipe shared notifications queued successfully",
                queued_count=response_data.queued_count,
            )

            return Response(
                response_data.model_dump(),
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception:
            # Let DRF exception handler handle it
            # (RecipeNotFoundError, PermissionDenied, etc.)
            raise


class RecipeCollectedView(APIView):
    """API endpoint for sending recipe collected notifications.

    Sends email notification when a recipe is added to a collection.
    Privacy-aware: collector identity revealed only if they follow recipe author.
    Requires notification:user or notification:admin scope.
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """Handle POST request to send recipe collected notifications.

        Args:
            request: HTTP request object containing recipient_ids, recipe_id,
                collector_id, and collection_id

        Returns:
            202 Accepted with BatchNotificationResponse if successful
            400 Bad Request if validation fails
            401 Unauthorized if authentication fails
            403 Forbidden if user lacks required scope or permissions
            404 Not Found if recipe, collection, or user doesn't exist
            429 Too Many Requests if rate limit exceeded
            500 Internal Server Error for unexpected errors
        """
        logger.info(
            "Recipe collected notification request received",
            user_id=request.user.user_id if request.user else None,
        )

        # Check user has required scope
        if not request.user.has_scope(
            "notification:user"
        ) and not request.user.has_scope("notification:admin"):
            logger.warning(
                "User lacks required scope for recipe notifications",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": ("You do not have permission to perform this action"),
                    "detail": (
                        "Requires notification:user or notification:admin scope"
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate request body with Pydantic
        try:
            recipe_collected_request = RecipeCollectedRequest(**request.data)
        except ValidationError as e:
            logger.warning(
                "Invalid request body for recipe collected notification",
                validation_errors=e.errors(),
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid request parameters",
                    "errors": e.errors(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call service to send notifications
        try:
            response_data = (
                social_notification_service.send_recipe_collected_notifications(
                    request=recipe_collected_request,
                )
            )

            logger.info(
                "Recipe collected notifications queued successfully",
                queued_count=response_data.queued_count,
            )

            return Response(
                response_data.model_dump(),
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception:
            # Let DRF exception handler handle it
            # (RecipeNotFoundError, CollectionNotFoundError, etc.)
            raise


class RecipeRatedView(APIView):
    """API endpoint for sending recipe rated notifications.

    Sends email notification when a recipe is rated.
    Privacy-aware: rater identity revealed only if they follow recipe author.
    Requires notification:user or notification:admin scope.
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """Handle POST request to send recipe rated notifications.

        Args:
            request: HTTP request object containing recipient_ids, recipe_id,
                and rater_id

        Returns:
            202 Accepted with BatchNotificationResponse if successful
            400 Bad Request if validation fails
            401 Unauthorized if authentication fails
            403 Forbidden if user lacks required scope or permissions
            404 Not Found if recipe or user doesn't exist
            429 Too Many Requests if rate limit exceeded
            500 Internal Server Error for unexpected errors
        """
        logger.info(
            "Recipe rated notification request received",
            user_id=request.user.user_id if request.user else None,
        )

        # Check user has required scope
        if not request.user.has_scope(
            "notification:user"
        ) and not request.user.has_scope("notification:admin"):
            logger.warning(
                "User lacks required scope for recipe notifications",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": ("You do not have permission to perform this action"),
                    "detail": (
                        "Requires notification:user or notification:admin scope"
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate request body with Pydantic
        try:
            recipe_rated_request = RecipeRatedRequest(**request.data)
        except ValidationError as e:
            logger.warning(
                "Invalid request body for recipe rated notification",
                validation_errors=e.errors(),
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid request parameters",
                    "errors": e.errors(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call service to send notifications
        try:
            response_data = recipe_notification_service.send_recipe_rated_notifications(
                request=recipe_rated_request,
            )

            logger.info(
                "Recipe rated notifications queued successfully",
                queued_count=response_data.queued_count,
            )

            return Response(
                response_data.model_dump(),
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception:
            # Let DRF exception handler handle it
            # (RecipeNotFoundError, UserNotFoundError, ValueError, etc.)
            raise


class RecipeFeaturedView(APIView):
    """API endpoint for sending recipe featured notifications.

    Sends email notification when a recipe is featured by the platform.
    Requires notification:admin scope only (system-generated notification).
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """Handle POST request to send recipe featured notifications.

        Args:
            request: HTTP request object containing recipient_ids, recipe_id,
                and optional featured_reason

        Returns:
            202 Accepted with BatchNotificationResponse if successful
            400 Bad Request if validation fails
            401 Unauthorized if authentication fails
            403 Forbidden if user lacks notification:admin scope
            404 Not Found if recipe or user doesn't exist
            429 Too Many Requests if rate limit exceeded
            500 Internal Server Error for unexpected errors
        """
        logger.info(
            "Recipe featured notification request received",
            user_id=request.user.user_id if request.user else None,
        )

        # Check user has admin scope (admin only)
        if not request.user.has_scope("notification:admin"):
            logger.warning(
                "User lacks required admin scope for recipe featured notifications",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": ("You do not have permission to perform this action"),
                    "detail": "Requires notification:admin scope",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate request body with Pydantic
        try:
            recipe_featured_request = RecipeFeaturedRequest(**request.data)
        except ValidationError as e:
            logger.warning(
                "Invalid request body for recipe featured notification",
                validation_errors=e.errors(),
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid request parameters",
                    "errors": e.errors(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call service to send notifications
        try:
            response_data = (
                recipe_notification_service.send_recipe_featured_notifications(
                    request=recipe_featured_request,
                )
            )

            logger.info(
                "Recipe featured notifications queued successfully",
                queued_count=response_data.queued_count,
            )

            return Response(
                response_data.model_dump(),
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception:
            # Let DRF exception handler handle it
            # (RecipeNotFoundError, UserNotFoundError, etc.)
            raise


class RecipeTrendingView(APIView):
    """API endpoint for sending recipe trending notifications.

    Sends email notification when a recipe is trending on the platform.
    Requires notification:admin scope only (system-generated notification).
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """Handle POST request to send recipe trending notifications.

        Args:
            request: HTTP request object containing recipient_ids, recipe_id,
                and optional trending_metrics

        Returns:
            202 Accepted with BatchNotificationResponse if successful
            400 Bad Request if validation fails
            401 Unauthorized if authentication fails
            403 Forbidden if user lacks admin scope
            404 Not Found if recipe or recipient user doesn't exist
            429 Too Many Requests if rate limit exceeded
            500 Internal Server Error for unexpected errors
        """
        logger.info(
            "Recipe trending notification request received",
            user_id=request.user.user_id,
        )

        if not request.user.has_scope("notification:admin"):
            logger.warning(
                "Recipe trending notification rejected - insufficient scope",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": "You do not have permission to perform this action",
                    "detail": "Requires notification:admin scope",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            recipe_trending_request = RecipeTrendingRequest(**request.data)
        except ValidationError as e:
            logger.warning(
                "Recipe trending notification validation failed",
                errors=e.errors(),
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid request parameters",
                    "errors": e.errors(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            response_data = (
                recipe_notification_service.send_recipe_trending_notifications(
                    request=recipe_trending_request,
                )
            )

            logger.info(
                "Recipe trending notifications queued successfully",
                queued_count=response_data.queued_count,
            )

            return Response(
                response_data.model_dump(),
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception:
            # Let DRF exception handler handle it
            # (RecipeNotFoundError, UserNotFoundError, etc.)
            raise


class NewFollowerView(APIView):
    """API endpoint for sending new follower notifications.

    Sends email notifications when a user gains a new follower.
    Requires notification:admin scope.
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """Handle POST request to send new follower notifications.

        Args:
            request: HTTP request object containing recipient_ids and
                follower_id

        Returns:
            202 Accepted with BatchNotificationResponse if successful
            400 Bad Request if validation fails
            401 Unauthorized if authentication fails
            403 Forbidden if user lacks admin scope or relationship
                doesn't exist
            404 Not Found if follower or recipient user doesn't exist
            429 Too Many Requests if rate limit exceeded
            500 Internal Server Error for unexpected errors
        """
        logger.info(
            "New follower notification request received",
            user_id=request.user.user_id if request.user else None,
        )

        # Check user has required scope (admin only)
        if not request.user.has_scope("notification:admin"):
            logger.warning(
                "User lacks required scope for new follower notifications",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": ("You do not have permission to perform this action"),
                    "detail": "Requires notification:admin scope",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate request body with Pydantic
        try:
            new_follower_request = NewFollowerRequest(**request.data)
        except ValidationError as e:
            logger.warning(
                "Invalid request body for new follower notification",
                validation_errors=e.errors(),
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid request parameters",
                    "errors": e.errors(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call service to send notifications
        try:
            response_data = social_notification_service.send_new_follower_notifications(
                request=new_follower_request,
            )

            logger.info(
                "New follower notifications queued successfully",
                queued_count=response_data.queued_count,
            )

            return Response(
                response_data.model_dump(),
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception:
            # Let DRF exception handler handle it
            # (UserNotFoundError, PermissionDenied, etc.)
            raise


class MentionView(APIView):
    """API endpoint for sending mention notifications.

    Sends email notifications when users are mentioned in comments.
    Requires notification:admin scope.
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """Handle POST request to send mention notifications.

        Args:
            request: HTTP request object containing recipient_ids and
                comment_id

        Returns:
            202 Accepted with BatchNotificationResponse if successful
            400 Bad Request if validation fails
            401 Unauthorized if authentication fails
            403 Forbidden if user lacks admin scope
            404 Not Found if comment, recipe, commenter, or recipient
                doesn't exist
            429 Too Many Requests if rate limit exceeded
            500 Internal Server Error for unexpected errors
        """
        logger.info(
            "Mention notification request received",
            user_id=request.user.user_id if request.user else None,
        )

        # Check user has required scope (user or admin)
        if not (
            request.user.has_scope("notification:user")
            or request.user.has_scope("notification:admin")
        ):
            logger.warning(
                "User lacks required scope for mention notifications",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": ("You do not have permission to perform this action"),
                    "detail": "Requires notification:user or notification:admin scope",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate request body with Pydantic
        try:
            mention_request = MentionRequest(**request.data)
        except ValidationError as e:
            logger.warning(
                "Invalid request body for mention notification",
                validation_errors=e.errors(),
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid request parameters",
                    "errors": e.errors(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call service to send notifications
        try:
            response_data = social_notification_service.send_mention_notifications(
                request=mention_request,
            )

            logger.info(
                "Mention notifications queued successfully",
                queued_count=response_data.queued_count,
            )

            return Response(
                response_data.model_dump(),
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception:
            # Let DRF exception handler handle it
            # (CommentNotFoundError, RecipeNotFoundError,
            # UserNotFoundError, PermissionDenied, etc.)
            raise


class PasswordResetView(APIView):
    """API endpoint for sending password reset notifications.

    Sends email notifications with password reset links.
    Requires notification:admin scope.
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """Handle POST request to send password reset notifications.

        Args:
            request: HTTP request object containing recipient_ids,
                reset_token, and expiry_hours

        Returns:
            202 Accepted with BatchNotificationResponse if successful
            400 Bad Request if validation fails
            401 Unauthorized if authentication fails
            403 Forbidden if user lacks admin scope
            404 Not Found if recipient user doesn't exist
            429 Too Many Requests if rate limit exceeded
            500 Internal Server Error for unexpected errors
        """
        logger.info(
            "Password reset notification request received",
            user_id=request.user.user_id if request.user else None,
        )

        # Check user has required scope (admin only)
        if not request.user.has_scope("notification:admin"):
            logger.warning(
                "User lacks required scope for password reset notifications",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": ("You do not have permission to perform this action"),
                    "detail": "Requires notification:admin scope",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate request body with Pydantic
        try:
            password_reset_request = PasswordResetRequest(**request.data)
        except ValidationError as e:
            logger.warning(
                "Invalid request body for password reset notification",
                validation_errors=e.errors(),
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid request parameters",
                    "errors": e.errors(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call service to send notifications
        try:
            response_data = (
                system_notification_service.send_password_reset_notifications(
                    request=password_reset_request,
                )
            )

            logger.info(
                "Password reset notifications queued successfully",
                queued_count=response_data.queued_count,
            )

            return Response(
                response_data.model_dump(),
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception:
            # Let DRF exception handler handle it
            # (UserNotFoundError, PermissionDenied, etc.)
            raise


class WelcomeView(APIView):
    """API endpoint for sending welcome notifications to new users.

    Sends email notifications to welcome newly registered users.
    Requires service-to-service authentication (client_credentials grant).
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """Handle POST request to send welcome notifications.

        Args:
            request: HTTP request object containing recipient_ids

        Returns:
            202 Accepted with BatchNotificationResponse if successful
            400 Bad Request if validation fails
            401 Unauthorized if authentication fails
            403 Forbidden if not service-to-service authentication
            404 Not Found if recipient user doesn't exist
            429 Too Many Requests if rate limit exceeded
            500 Internal Server Error for unexpected errors
        """
        logger.info(
            "Welcome notification request received",
            client_id=request.user.client_id if request.user else None,
        )

        # Validate request body with Pydantic
        try:
            welcome_request = WelcomeRequest(**request.data)
        except ValidationError as e:
            logger.warning(
                "Invalid request body for welcome notification",
                validation_errors=e.errors(),
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid request parameters",
                    "errors": e.errors(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call service to send notifications
        try:
            response_data = system_notification_service.send_welcome_notifications(
                request=welcome_request,
            )

            logger.info(
                "Welcome notifications queued successfully",
                queued_count=response_data.queued_count,
            )

            return Response(
                response_data.model_dump(),
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception:
            # Let DRF exception handler handle it
            # (UserNotFoundError, PermissionDenied, etc.)
            raise


class EmailChangedView(APIView):
    """API endpoint for sending email change notifications.

    Sends security notifications when a user's email address is changed.
    Notifications are sent to both the old and new email addresses.
    Requires service-to-service authentication (client_credentials grant).
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """Handle POST request to send email changed notifications.

        Args:
            request: HTTP request object containing recipient_ids,
                old_email, and new_email

        Returns:
            202 Accepted with BatchNotificationResponse if successful
            400 Bad Request if validation fails
            401 Unauthorized if authentication fails
            403 Forbidden if not service-to-service authentication
            404 Not Found if recipient user doesn't exist
            429 Too Many Requests if rate limit exceeded
            500 Internal Server Error for unexpected errors
        """
        logger.info(
            "Email changed notification request received",
            client_id=request.user.client_id if request.user else None,
        )

        # Validate request body with Pydantic
        try:
            email_changed_request = EmailChangedRequest(**request.data)
        except ValidationError as e:
            logger.warning(
                "Invalid request body for email changed notification",
                validation_errors=e.errors(),
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid request parameters",
                    "errors": e.errors(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call service to send notifications
        try:
            response_data = (
                system_notification_service.send_email_changed_notifications(
                    request=email_changed_request,
                )
            )

            logger.info(
                "Email changed notifications queued successfully",
                queued_count=response_data.queued_count,
            )

            return Response(
                response_data.model_dump(),
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception:
            # Let DRF exception handler handle it
            # (UserNotFoundError, PermissionDenied, etc.)
            raise


class NotificationDetailView(APIView):
    """API endpoint for retrieving and deleting individual notifications.

    GET: Retrieve notification details
    DELETE: Delete a notification
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request, notification_id):
        """Retrieve notification by ID.

        Authorization:
        - Admin scope: Can view any notification
        - User scope: Can only view their own notifications

        Query parameters:
        - include_message: Set to 'true' to include the full message body

        Args:
            request: HTTP request
            notification_id: UUID of the notification

        Returns:
            Response with notification details
        """
        logger.info(
            "Notification detail request received",
            notification_id=notification_id,
            user_id=request.user.user_id if request.user else None,
        )

        # Validate UUID format
        try:
            notification_id_uuid = UUID(notification_id)
        except ValueError:
            logger.warning(
                "Invalid notification ID format",
                notification_id=notification_id,
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid notification ID format",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get include_message query parameter (default: false)
        include_message = (
            request.query_params.get("include_message", "false").lower() == "true"
        )

        # Get notification (service handles authorization)
        try:
            notification = notification_service.get_notification_for_user(
                notification_id=notification_id_uuid,
                include_message=include_message,
            )

            # Serialize notification
            notification_detail = NotificationDetail.model_validate(notification)

            # Exclude message if not requested
            if include_message:
                response_data = notification_detail.model_dump()
            else:
                response_data = notification_detail.model_dump(exclude={"message"})

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception:
            # Let DRF exception handler handle it
            # (Http404, PermissionDenied, etc.)
            raise

    def delete(self, request, notification_id):
        """Delete notification by ID.

        Authorization:
        - Admin scope: Can delete any notification
        - User scope: Can only delete their own notifications

        Cannot delete notifications in 'queued' status (returns 409).

        Args:
            request: HTTP request
            notification_id: UUID of the notification

        Returns:
            Response with 204 No Content on success
        """
        logger.info(
            "Notification deletion request received",
            notification_id=notification_id,
            user_id=request.user.user_id if request.user else None,
        )

        # Validate UUID format
        try:
            notification_id_uuid = UUID(notification_id)
        except ValueError:
            logger.warning(
                "Invalid notification ID format for deletion",
                notification_id=notification_id,
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid notification ID format",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Delete notification (service handles authorization and status checks)
        try:
            notification_service.delete_notification(
                notification_id=notification_id_uuid
            )

            logger.info(
                "Notification deleted successfully",
                notification_id=notification_id,
            )

            return Response(status=status.HTTP_204_NO_CONTENT)

        except Exception:
            # Let DRF exception handler handle it
            # (Http404, PermissionDenied, ConflictError, etc.)
            raise


class UserNotificationListView(APIView):
    """API endpoint for retrieving the authenticated user's notifications.

    GET: Retrieve paginated list of notifications for the current user
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        """Retrieve paginated notifications for the authenticated user.

        Authorization:
        - Requires notification:user OR notification:admin scope
        - Users can only see their own notifications

        Query parameters:
        - page: Page number (default: 1)
        - page_size: Items per page (default: 20, max: 100)
        - status: Filter by status (optional: pending, queued, sent, failed)
        - notification_type: Filter by type (optional: email)
        - include_message: Include message body (default: false)

        Args:
            request: HTTP request

        Returns:
            Response with paginated notification list
        """
        logger.info(
            "User notifications list request received",
            user_id=request.user.user_id if request.user else None,
        )

        # Check user has required scope
        if not request.user.has_scope(
            "notification:user"
        ) and not request.user.has_scope("notification:admin"):
            logger.warning(
                "User lacks required scope for notifications list",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": "You do not have permission to perform this action",
                    "detail": "Requires notification:user or notification:admin scope",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Parse query parameters
        status_filter = request.query_params.get("status", None)
        notification_type_filter = request.query_params.get("notification_type", None)
        include_message = (
            request.query_params.get("include_message", "false").lower() == "true"
        )

        # Validate status filter if provided
        if status_filter and status_filter not in [
            "pending",
            "queued",
            "sent",
            "failed",
        ]:
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid status filter",
                    "detail": "Status must be one of: pending, queued, sent, failed",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate notification_type filter if provided
        if notification_type_filter and notification_type_filter not in ["email"]:
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid notification_type filter",
                    "detail": "Notification type must be: email",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get notifications (service handles authorization)
        try:
            queryset = notification_service.get_my_notifications(
                status=status_filter,
                notification_type=notification_type_filter,
            )

            # Apply pagination
            paginator = NotificationPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(queryset, request)

            """
            Handle case where paginate_queryset returns None
            (shouldn't happen with valid requests)
            """
            if paginated_queryset is None:
                paginated_queryset = []

            # Serialize notifications
            notifications_data = []
            for notification in paginated_queryset:
                notification_detail = NotificationDetail.model_validate(notification)

                # Exclude message if not requested
                if include_message:
                    notifications_data.append(notification_detail.model_dump())
                else:
                    notifications_data.append(
                        notification_detail.model_dump(exclude={"message"})
                    )

            # Build paginated response using DRF's method
            # get_paginated_response returns a Response object
            paginated_response = paginator.get_paginated_response(notifications_data)

            logger.info(
                "User notifications list retrieved",
                user_id=request.user.user_id,
                count=len(notifications_data),
            )

            """
            get_paginated_response already returns a Response, so we return it directly
            """
            return paginated_response

        except Exception as e:
            # Log the exception for debugging
            logger.error(
                "Error retrieving user notifications",
                error=str(e),
                error_type=type(e).__name__,
                user_id=request.user.user_id if request.user else None,
                exc_info=True,
            )
            # Let DRF exception handler handle it
            # (PermissionDenied, etc.)
            raise


class UserNotificationsByIdView(APIView):
    """API endpoint for retrieving notifications for a specific user by user_id.

    GET: Retrieve paginated list of notifications for a specified user (admin only)
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request, user_id):
        """Retrieve paginated notifications for a specific user.

        Authorization:
        - Requires notification:admin scope only
        - Admin users can query notifications for any user

        Query parameters:
        - page: Page number (default: 1)
        - page_size: Items per page (default: 20, max: 100)
        - status: Filter by status (optional: pending, queued, sent, failed)
        - notification_type: Filter by type (optional: email)
        - include_message: Include message body (default: false)

        Args:
            request: HTTP request
            user_id: UUID of the user whose notifications to retrieve

        Returns:
            Response with paginated notification list
        """
        logger.info(
            "User notifications by ID request received",
            target_user_id=user_id,
            requester_user_id=request.user.user_id if request.user else None,
        )

        # Check user has admin scope (this endpoint is admin-only)
        if not request.user.has_scope("notification:admin"):
            logger.warning(
                "User lacks required scope for user notifications by ID",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
                target_user_id=user_id,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": "You do not have permission to perform this action",
                    "detail": "Requires notification:admin scope",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate user_id is a valid UUID
        try:
            user_id_uuid = UUID(user_id)
        except ValueError:
            logger.warning(
                "Invalid user ID format",
                user_id=user_id,
                requester_user_id=request.user.user_id,
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid user ID format",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Parse query parameters
        status_filter = request.query_params.get("status", None)
        notification_type_filter = request.query_params.get("notification_type", None)
        include_message = (
            request.query_params.get("include_message", "false").lower() == "true"
        )

        # Validate status filter if provided
        if status_filter and status_filter not in [
            "pending",
            "queued",
            "sent",
            "failed",
        ]:
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid status filter",
                    "detail": "Status must be one of: pending, queued, sent, failed",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate notification_type filter if provided
        if notification_type_filter and notification_type_filter not in ["email"]:
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid notification_type filter",
                    "detail": "Notification type must be: email",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get notifications (service handles user existence check)
        try:
            queryset = notification_service.get_user_notifications(
                user_id=user_id_uuid,
                status=status_filter,
                notification_type=notification_type_filter,
            )

            # Apply pagination
            paginator = NotificationPageNumberPagination()
            paginated_queryset = paginator.paginate_queryset(queryset, request)

            """
            Handle case where paginate_queryset returns None
            (shouldn't happen with valid requests)
            """
            if paginated_queryset is None:
                paginated_queryset = []

            # Serialize notifications
            notifications_data = []
            for notification in paginated_queryset:
                notification_detail = NotificationDetail.model_validate(notification)

                # Exclude message if not requested
                if include_message:
                    notifications_data.append(notification_detail.model_dump())
                else:
                    notifications_data.append(
                        notification_detail.model_dump(exclude={"message"})
                    )

            # Build paginated response using DRF's method
            # get_paginated_response returns a Response object
            paginated_response = paginator.get_paginated_response(notifications_data)

            logger.info(
                "User notifications by ID retrieved",
                target_user_id=user_id,
                requester_user_id=request.user.user_id,
                count=len(notifications_data),
            )

            """
            get_paginated_response already returns a Response, so we return it directly
            """
            return paginated_response

        except Exception as e:
            # Log the exception for debugging
            logger.error(
                "Error retrieving user notifications by ID",
                error=str(e),
                error_type=type(e).__name__,
                target_user_id=user_id,
                requester_user_id=request.user.user_id if request.user else None,
                exc_info=True,
            )
            # Let DRF exception handler handle it
            # (UserNotFoundError will be caught by global exception handler)
            raise


class NotificationStatsView(APIView):
    """API endpoint for retrieving notification statistics.

    GET: Retrieve comprehensive notification statistics (admin only)
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        """Retrieve notification statistics with optional date range filtering.

        Authorization:
        - Requires notification:admin scope

        Query Parameters:
        - start_date (optional): ISO 8601 datetime for start of range
        - end_date (optional): ISO 8601 datetime for end of range

        Returns:
            200 OK with NotificationStats if successful
            400 Bad Request if date parameters are invalid
            401 Unauthorized if authentication fails
            403 Forbidden if user lacks admin scope
            500 Internal Server Error for unexpected errors
        """
        logger.info(
            "Notification stats request received",
            user_id=request.user.user_id if request.user else None,
        )

        # Check user has admin scope
        if not request.user.has_scope("notification:admin"):
            logger.warning(
                "User lacks required scope for notification stats",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": "You do not have permission to perform this action",
                    "detail": "Requires notification:admin scope",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Parse optional date range query parameters
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")

        start_date = None
        end_date = None

        # Validate and parse start_date
        if start_date_str:
            try:
                start_date = datetime.fromisoformat(
                    start_date_str.replace("Z", "+00:00")
                )
            except (ValueError, AttributeError) as e:
                logger.warning(
                    "Invalid start_date format",
                    start_date=start_date_str,
                    error=str(e),
                )
                return Response(
                    {
                        "error": "bad_request",
                        "message": "Invalid start_date format",
                        "detail": (
                            "Expected ISO 8601 format (e.g., 2025-10-01T00:00:00Z)"
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Validate and parse end_date
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError) as e:
                logger.warning(
                    "Invalid end_date format",
                    end_date=end_date_str,
                    error=str(e),
                )
                return Response(
                    {
                        "error": "bad_request",
                        "message": "Invalid end_date format",
                        "detail": (
                            "Expected ISO 8601 format (e.g., 2025-10-28T23:59:59Z)"
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Validate date range logic
        if start_date and end_date and start_date > end_date:
            logger.warning(
                "Invalid date range",
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid date range",
                    "detail": "start_date must be before or equal to end_date",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call service to get stats
        try:
            stats = admin_service.get_notification_stats(
                start_date=start_date,
                end_date=end_date,
            )

            # Validate with Pydantic schema
            stats_response = NotificationStats(**stats)

            logger.info(
                "Notification stats retrieved successfully",
                total=stats["total_notifications"],
                sent=stats["status_breakdown"]["sent"],
                failed=stats["status_breakdown"]["failed"],
            )

            return Response(
                stats_response.model_dump(),
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            # Log the exception for debugging
            logger.error(
                "Error retrieving notification stats",
                error=str(e),
                error_type=type(e).__name__,
                user_id=request.user.user_id if request.user else None,
                exc_info=True,
            )
            # Let DRF exception handler handle it
            raise


class RetryFailedNotificationsView(APIView):
    """API endpoint for retrying failed notifications.

    POST: Queue failed notifications for retry (admin only)
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """Retry failed notifications with batch size limit.

        Authorization:
        - Requires notification:admin scope

        Query Parameters:
        - max_failures (optional): Maximum number to retry (1-1000, default: 100)

        Returns:
            202 Accepted with retry results if successful
            400 Bad Request if parameters are invalid
            401 Unauthorized if authentication fails
            403 Forbidden if user lacks admin scope
            500 Internal Server Error for unexpected errors
        """
        logger.info(
            "Retry failed notifications request received",
            user_id=request.user.user_id if request.user else None,
        )

        # Check user has admin scope
        if not request.user.has_scope("notification:admin"):
            logger.warning(
                "User lacks required scope for retry failed notifications",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": "You do not have permission to perform this action",
                    "detail": "Requires notification:admin scope",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Parse and validate max_failures parameter
        max_failures_str = request.query_params.get("max_failures", "100")

        try:
            max_failures = int(max_failures_str)
        except (ValueError, TypeError):
            logger.warning(
                "Invalid max_failures parameter",
                max_failures=max_failures_str,
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid max_failures parameter",
                    "detail": "max_failures must be an integer",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate range
        if max_failures < 1 or max_failures > 1000:
            logger.warning(
                "max_failures out of valid range",
                max_failures=max_failures,
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid max_failures parameter",
                    "detail": "max_failures must be between 1 and 1000",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Call service to retry failed notifications
        try:
            result = admin_service.retry_failed_notifications(max_failures=max_failures)

            message = (
                f"{result['queued_count']} of {result['total_eligible']} "
                "failed notifications queued for retry"
            )

            logger.info(
                "Failed notifications retry completed",
                queued_count=result["queued_count"],
                total_eligible=result["total_eligible"],
                remaining_failed=result["remaining_failed"],
            )

            return Response(
                {
                    "queued_count": result["queued_count"],
                    "remaining_failed": result["remaining_failed"],
                    "total_eligible": result["total_eligible"],
                    "message": message,
                },
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception as e:
            # Log the exception for debugging
            logger.error(
                "Error retrying failed notifications",
                error=str(e),
                error_type=type(e).__name__,
                user_id=request.user.user_id if request.user else None,
                exc_info=True,
            )
            # Let DRF exception handler handle it
            raise


class NotificationRetryStatusView(APIView):
    """API endpoint for checking retry status.

    GET: Get current retry status for failed notifications (admin only)
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        """Get current retry status.

        Authorization:
        - Requires notification:admin scope

        Returns:
            200 OK with retry status if successful
            401 Unauthorized if authentication fails
            403 Forbidden if user lacks admin scope
            500 Internal Server Error for unexpected errors
        """
        logger.info(
            "Retry status request received",
            user_id=request.user.user_id if request.user else None,
        )

        # Check user has admin scope
        if not request.user.has_scope("notification:admin"):
            logger.warning(
                "User lacks required scope for retry status",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": "You do not have permission to perform this action",
                    "detail": "Requires notification:admin scope",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Call service to get retry status
        try:
            retry_status = admin_service.get_retry_status()

            logger.info(
                "Retry status retrieved successfully",
                failed_retryable=retry_status["failed_retryable"],
                failed_exhausted=retry_status["failed_exhausted"],
                currently_queued=retry_status["currently_queued"],
                safe_to_retry=retry_status["safe_to_retry"],
            )

            return Response(
                retry_status,
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            # Log the exception for debugging
            logger.error(
                "Error retrieving retry status",
                error=str(e),
                error_type=type(e).__name__,
                user_id=request.user.user_id if request.user else None,
                exc_info=True,
            )
            # Let DRF exception handler handle it
            raise


class RetryNotificationView(APIView):
    """View for retrying a single failed notification.

    Endpoint: POST /notifications/{notification_id}/retry

    Requires notification:admin scope.
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request, notification_id):
        """Retry a failed notification.

        Args:
            request: HTTP request
            notification_id: UUID string of notification to retry

        Returns:
            202: Notification queued for retry
            400: Invalid notification ID format
            401: Not authenticated
            403: Insufficient permissions (requires admin scope)
            404: Notification not found
            409: Cannot retry (wrong status or retries exhausted)
            500: Server error
        """
        logger.info(
            "Retry single notification request received",
            user_id=request.user.user_id if request.user else None,
            notification_id=notification_id,
        )

        # Check user has required scope (admin only)
        if not request.user.has_scope("notification:admin"):
            logger.warning(
                "User lacks required scope for retry notification",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": ("You do not have permission to perform this action"),
                    "detail": "Requires notification:admin scope",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate UUID format
        try:
            notification_id_uuid = UUID(notification_id)
        except ValueError:
            logger.warning(
                "Invalid notification ID format for retry",
                user_id=request.user.user_id,
                notification_id=notification_id,
            )
            return Response(
                {
                    "error": "bad_request",
                    "message": "Invalid notification ID format",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Call admin service to retry the notification
            result = admin_service.retry_single_notification(notification_id_uuid)

            logger.info(
                "Notification retry request successful",
                user_id=request.user.user_id,
                notification_id=str(notification_id_uuid),
            )

            return Response(result, status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            logger.error(
                "Error retrying notification",
                error=str(e),
                error_type=type(e).__name__,
                user_id=request.user.user_id if request.user else None,
                notification_id=notification_id,
                exc_info=True,
            )
            # Let DRF exception handler handle it (Http404, ConflictError, etc.)
            raise


class TemplateListView(APIView):
    """API endpoint for listing available notification templates.

    GET: Retrieve list of all available notification templates
    """

    authentication_classes = (OAuth2Authentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        """Retrieve list of available notification templates.

        Authorization:
        - Requires notification:user OR notification:admin scope

        Returns:
            200 OK with list of templates if successful
            401 Unauthorized if authentication fails
            403 Forbidden if user lacks required scope
            500 Internal Server Error for unexpected errors
        """
        logger.info(
            "Template list request received",
            user_id=request.user.user_id if request.user else None,
        )

        # Check user has required scope
        if not request.user.has_scope(
            "notification:user"
        ) and not request.user.has_scope("notification:admin"):
            logger.warning(
                "User lacks required scope for template list",
                user_id=request.user.user_id,
                scopes=request.user.scopes,
            )
            return Response(
                {
                    "error": "forbidden",
                    "message": "You do not have permission to perform this action",
                    "detail": "Requires notification:user or notification:admin scope",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get templates from service
        try:
            templates = admin_service.get_all_templates()

            # Validate with Pydantic schema
            response_data = TemplateListResponse(templates=templates)

            logger.info(
                "Template list retrieved successfully",
                template_count=len(templates),
            )

            return Response(
                response_data.model_dump(),
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            # Log the exception for debugging
            logger.error(
                "Error retrieving template list",
                error=str(e),
                error_type=type(e).__name__,
                user_id=request.user.user_id if request.user else None,
                exc_info=True,
            )
            # Let DRF exception handler handle it
            raise
