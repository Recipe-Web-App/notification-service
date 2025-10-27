"""Security headers middleware for enhanced security."""

import logging
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from core.constants import SECURITY_HEADERS

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware:
    """Middleware to add security headers to all responses.

    This middleware adds standard security headers to protect against
    common web vulnerabilities:

    - X-Frame-Options: Prevents clickjacking attacks
    - X-Content-Type-Options: Prevents MIME type sniffing
    - X-XSS-Protection: Enables browser XSS protection
    - Strict-Transport-Security: Enforces HTTPS connections
    - Referrer-Policy: Controls referrer information
    - Content-Security-Policy: Restricts resource loading

    These headers provide defense-in-depth security for the application.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Initialize the middleware.

        Args:
            get_response: The next middleware or view in the chain.
        """
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request and add security headers to the response.

        Args:
            request: The incoming HTTP request.

        Returns:
            The HTTP response with security headers added.
        """
        response = self.get_response(request)

        # Add all security headers to the response
        for header, value in SECURITY_HEADERS.items():
            response[header] = value

        return response
