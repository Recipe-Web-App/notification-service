"""Thread-local context management for security/authentication."""

import threading

from rest_framework.exceptions import AuthenticationFailed

from core.auth.oauth2 import OAuth2User

# Thread-local storage for security context
_security_context = threading.local()


def set_current_user(user: OAuth2User) -> None:
    """Store the authenticated user in thread-local storage.

    Args:
        user: The authenticated OAuth2User to store.
    """
    _security_context.user = user


def get_current_user() -> OAuth2User | None:
    """Retrieve the authenticated user from thread-local storage.

    Returns:
        The current authenticated user, or None if not set.
    """
    return getattr(_security_context, "user", None)


def require_current_user() -> OAuth2User:
    """Retrieve the authenticated user or raise an exception.

    Returns:
        The current authenticated user.

    Raises:
        AuthenticationFailed: If no user is set in the security context.
    """
    user = get_current_user()
    if user is None:
        raise AuthenticationFailed("Authentication required")
    return user


def clear_current_user() -> None:
    """Clear the authenticated user from thread-local storage.

    This should be called after request processing is complete
    to prevent memory leaks and context bleeding between requests.
    """
    if hasattr(_security_context, "user"):
        delattr(_security_context, "user")
