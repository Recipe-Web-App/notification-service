"""API views for core application."""

import structlog
from pydantic import ValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.auth.oauth2 import OAuth2Authentication
from core.schemas.notification import (
    NewFollowerRequest,
    RecipeCommentedRequest,
    RecipeLikedRequest,
    RecipePublishedRequest,
)
from core.services import health_service
from core.services.recipe_notification_service import (
    recipe_notification_service,
)
from core.services.social_notification_service import (
    social_notification_service,
)

logger = structlog.get_logger(__name__)


class HealthCheckView(APIView):
    """Simple health check endpoint.

    This endpoint is exempt from authentication to allow Kubernetes probes
    and monitoring systems to check service health.
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
        """Handle GET request for health check.

        Args:
            _request: HTTP request object (unused).

        Returns:
            Response object with status OK.
        """
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


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
                    authenticated_user=request.user,
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
                authenticated_user=request.user,
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
                    authenticated_user=request.user,
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
                authenticated_user=request.user,
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
