"""Request ID middleware for distributed tracing."""

import logging
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from core.constants import REQUEST_ID_HEADER
from core.logging.context import clear_request_id, set_request_id

logger = logging.getLogger(__name__)


class RequestIDMiddleware:
    """Middleware to handle request ID for distributed tracing.

    This middleware:
    - Checks for an existing X-Request-ID header in the incoming request
    - Generates a new UUID if no request ID is present
    - Stores the request ID in thread-local storage for logging
    - Adds the request ID to the response headers
    - Cleans up the thread-local storage after the request completes

    The request ID enables correlation of logs and requests across
    multiple services in a distributed system.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Initialize the middleware.

        Args:
            get_response: The next middleware or view in the chain.
        """
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request and add request ID tracking.

        Args:
            request: The incoming HTTP request.

        Returns:
            The HTTP response with request ID header added.
        """
        # Get or generate request ID
        request_id = request.headers.get(REQUEST_ID_HEADER)
        if not request_id:
            request_id = str(uuid.uuid4())

        # Store in thread-local storage for logging
        set_request_id(request_id)

        # Store on request object for easy access by views
        request.request_id = request_id  # type: ignore[attr-defined]

        try:
            # Process the request
            response = self.get_response(request)

            # Add request ID to response headers
            response[REQUEST_ID_HEADER] = request_id

            return response
        finally:
            # Always clean up thread-local storage to prevent memory leaks
            clear_request_id()
