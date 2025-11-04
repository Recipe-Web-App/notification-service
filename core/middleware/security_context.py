"""Security context middleware for authenticated user access."""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from django.http import HttpRequest, HttpResponse

from core.auth.context import clear_current_user, set_current_user

if TYPE_CHECKING:
    from core.auth.oauth2 import OAuth2User

logger = logging.getLogger(__name__)


class SecurityContextMiddleware:
    """Middleware to store authenticated user in thread-local storage.

    This middleware:
    - Stores the authenticated user (if present) in thread-local storage
    - Makes the user accessible via get_current_user() throughout the request
    - Cleans up the thread-local storage after the request completes

    This enables service layer methods to access the authenticated user
    without requiring it to be passed as a parameter through every method call.

    Note: This middleware should be placed AFTER authentication middleware
    in the MIDDLEWARE list to ensure request.user is populated.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Initialize the middleware.

        Args:
            get_response: The next middleware or view in the chain.
        """
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request and manage security context.

        Args:
            request: The incoming HTTP request.

        Returns:
            The HTTP response.
        """
        # Store authenticated user in thread-local storage if present
        if hasattr(request, "user") and request.user and request.user.is_authenticated:
            # Cast to OAuth2User since our authentication sets this type
            oauth2_user = cast("OAuth2User", request.user)
            set_current_user(oauth2_user)
            logger.debug(
                "Security context set for user",
                extra={"user_id": getattr(request.user, "user_id", None)},
            )

        try:
            # Process the request
            response = self.get_response(request)
            return response
        finally:
            # Always clean up thread-local storage to prevent memory leaks
            # and context bleeding between requests
            clear_current_user()
