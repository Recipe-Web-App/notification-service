"""Process time middleware for performance monitoring."""

import logging
import time
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from core.constants import PROCESS_TIME_HEADER, SLOW_REQUEST_THRESHOLD

logger = logging.getLogger(__name__)


class ProcessTimeMiddleware:
    """Middleware to track request processing time.

    This middleware:
    - Records the start time when a request begins
    - Calculates the duration when the request completes
    - Adds the X-Process-Time header to the response
    - Logs slow requests (those exceeding the threshold)

    This enables performance monitoring and identification of slow endpoints.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Initialize the middleware.

        Args:
            get_response: The next middleware or view in the chain.
        """
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request and track its duration.

        Args:
            request: The incoming HTTP request.

        Returns:
            The HTTP response with process time header added.
        """
        # Record start time
        start_time = time.time()

        # Process the request
        response = self.get_response(request)

        # Calculate duration
        duration = time.time() - start_time

        # Add process time header (in seconds)
        response[PROCESS_TIME_HEADER] = f"{duration:.6f}"

        # Log slow requests
        if duration > SLOW_REQUEST_THRESHOLD:
            logger.warning(
                f"Slow request detected: {request.method} {request.path} "
                f"took {duration:.2f}s (threshold: {SLOW_REQUEST_THRESHOLD}s)"
            )

        return response
