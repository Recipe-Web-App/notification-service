"""API views for core application."""

from uuid import UUID

import structlog
from pydantic import ValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.auth.oauth2 import OAuth2Authentication
from core.schemas.notification import (
    MentionRequest,
    NewFollowerRequest,
    NotificationDetail,
    PasswordResetRequest,
    RecipeCommentedRequest,
    RecipeLikedRequest,
    RecipePublishedRequest,
)
from core.services import health_service
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

        # Check user has required scope (admin only)
        if not request.user.has_scope("notification:admin"):
            logger.warning(
                "User lacks required scope for mention notifications",
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
