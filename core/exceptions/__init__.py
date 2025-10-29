"""Exception handling utilities for the notification service."""

from core.exceptions.downstream_exceptions import (
    DownstreamServiceError,
    DownstreamServiceUnavailableError,
    RecipeNotFoundError,
    UserNotFoundError,
)
from core.exceptions.handlers import custom_exception_handler

__all__ = [
    "DownstreamServiceError",
    "DownstreamServiceUnavailableError",
    "RecipeNotFoundError",
    "UserNotFoundError",
    "custom_exception_handler",
]
