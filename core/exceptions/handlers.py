"""Global exception handlers for the notification service."""

import logging
import traceback
from datetime import UTC, datetime
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

from core.exceptions.downstream_exceptions import (
    CommentNotFoundError,
    ConflictError,
    RecipeNotFoundError,
    UserNotFoundError,
)
from core.logging.context import get_request_id

logger = logging.getLogger(__name__)


def custom_exception_handler(
    exc: Exception, context: dict[str, Any]
) -> Response | None:
    """Custom exception handler for Django REST Framework.

    Handles both DRF and Django exceptions, providing:
    - Standard response format for clients: {status, message, request_id, timestamp}
    - Detailed logging for troubleshooting: error type, path, stack trace, request info

    Args:
        exc: The exception that was raised.
        context: Context dictionary containing request and view information.

    Returns:
        A Response object with the error details, or None for unhandled exceptions.
    """
    # Get the request from context
    view = context.get("view")
    request = view.request if view else None
    request_id = get_request_id()

    # Let DRF handle its own exceptions first
    response = exception_handler(exc, context)

    # If DRF didn't handle it, handle Django exceptions and custom exceptions
    if response is None:
        if isinstance(
            exc, (CommentNotFoundError, RecipeNotFoundError, UserNotFoundError)
        ):
            response_data = _create_error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message=str(exc),
                request_id=request_id,
            )
            response = Response(response_data, status=status.HTTP_404_NOT_FOUND)
        elif isinstance(exc, ConflictError):
            response_data = {
                "error": "conflict",
                "message": str(exc),
                "detail": exc.detail if hasattr(exc, "detail") else None,
                "request_id": request_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            response = Response(response_data, status=status.HTTP_409_CONFLICT)
        elif isinstance(exc, Http404):
            response_data = _create_error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                message="The requested resource was not found.",
                request_id=request_id,
            )
            response = Response(response_data, status=status.HTTP_404_NOT_FOUND)
        elif isinstance(exc, PermissionDenied):
            response_data = _create_error_response(
                status_code=status.HTTP_403_FORBIDDEN,
                message="You do not have permission to perform this action.",
                request_id=request_id,
            )
            response = Response(response_data, status=status.HTTP_403_FORBIDDEN)
        else:
            # Unhandled exception - log as error and return 500
            response_data = _create_error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                message="An internal server error occurred.",
                request_id=request_id,
            )
            response = Response(
                response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # Add request ID to response if available
    if request_id and response:
        response["X-Request-ID"] = request_id

    # Log detailed error information
    _log_exception(exc, request, response)

    return response


def _create_error_response(
    status_code: int, message: str, request_id: str | None
) -> dict[str, Any]:
    """Create a standardized error response.

    Args:
        status_code: The HTTP status code.
        message: The error message to return to the client.
        request_id: The request ID for tracing.

    Returns:
        Dictionary with standard error response format.
    """
    return {
        "status": status_code,
        "message": message,
        "request_id": request_id,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def _log_exception(
    exc: Exception,
    request: Any,
    response: Response | None,
) -> None:
    """Log detailed exception information for troubleshooting.

    In DEBUG mode, logs include stack traces.
    In production, logs are more concise but still informative.

    Args:
        exc: The exception that was raised.
        request: The HTTP request object.
        response: The response object (if available).
    """
    # Determine log level based on exception type
    if isinstance(exc, (Http404, APIException)) and hasattr(exc, "status_code"):
        # Client errors (4xx) - log as warning
        if 400 <= getattr(exc, "status_code", 500) < 500:
            log_level = logging.WARNING
        else:
            log_level = logging.ERROR
    else:
        # Server errors and unknown exceptions - log as error
        log_level = logging.ERROR

    # Build detailed log message
    error_type = type(exc).__name__
    error_message = str(exc)
    request_path = request.path if request else "unknown"
    request_method = request.method if request else "unknown"
    status_code = response.status_code if response else "unknown"

    log_message = (
        f"Exception occurred: {error_type}: {error_message} | "
        f"Path: {request_method} {request_path} | "
        f"Status: {status_code}"
    )

    # Add stack trace in DEBUG mode
    if settings.DEBUG:
        stack_trace = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
        log_message += f"\nStack trace:\n{stack_trace}"

    # Add request details for debugging
    if request and settings.DEBUG:
        log_message += f"\nRequest details: {_get_request_details(request)}"

    # Log the exception
    logger.log(log_level, log_message)


def _get_request_details(request: Any) -> str:
    """Extract relevant request details for logging.

    Args:
        request: The HTTP request object.

    Returns:
        String with formatted request details.
    """
    details = {
        "method": request.method,
        "path": request.path,
        "user": getattr(request, "user", "anonymous"),
        "ip": request.META.get("REMOTE_ADDR", "unknown"),
    }

    # Add query params if present
    if request.GET:
        details["query_params"] = dict(request.GET)

    return str(details)
