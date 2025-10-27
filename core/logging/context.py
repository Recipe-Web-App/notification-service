"""Thread-local context management for request tracking."""

import threading

# Thread-local storage for request context
_request_context = threading.local()


def set_request_id(request_id: str) -> None:
    """Store the request ID in thread-local storage.

    Args:
        request_id: The unique request identifier to store.
    """
    _request_context.request_id = request_id


def get_request_id() -> str | None:
    """Retrieve the request ID from thread-local storage.

    Returns:
        The current request ID, or None if not set.
    """
    return getattr(_request_context, "request_id", None)


def clear_request_id() -> None:
    """Clear the request ID from thread-local storage.

    This should be called after request processing is complete
    to prevent memory leaks and context bleeding between requests.
    """
    if hasattr(_request_context, "request_id"):
        delattr(_request_context, "request_id")
