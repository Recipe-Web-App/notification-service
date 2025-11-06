"""Constants package for core application."""

# Re-export HTTP and performance constants for backward compatibility
from core.constants.http import (
    DEFAULT_RATE_LIMIT_REQUESTS,
    DEFAULT_RATE_LIMIT_WINDOW,
    PROCESS_TIME_HEADER,
    REQUEST_ID_HEADER,
    SECURITY_HEADERS,
    SLOW_REQUEST_THRESHOLD,
)

# Export template registry
from core.constants.templates import TEMPLATE_REGISTRY

__all__ = [
    "DEFAULT_RATE_LIMIT_REQUESTS",
    "DEFAULT_RATE_LIMIT_WINDOW",
    "PROCESS_TIME_HEADER",
    "REQUEST_ID_HEADER",
    "SECURITY_HEADERS",
    "SLOW_REQUEST_THRESHOLD",
    "TEMPLATE_REGISTRY",
]
