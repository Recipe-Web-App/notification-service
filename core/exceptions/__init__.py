"""Exception handling utilities for the notification service."""

from core.exceptions.downstream_exceptions import (
    CollectionNotFoundError,
    CommentNotFoundError,
    DownstreamServiceError,
    DownstreamServiceUnavailableError,
    RecipeNotFoundError,
    UserNotFoundError,
)
from core.exceptions.handlers import custom_exception_handler

__all__ = [
    "CollectionNotFoundError",
    "CommentNotFoundError",
    "DownstreamServiceError",
    "DownstreamServiceUnavailableError",
    "RecipeNotFoundError",
    "UserNotFoundError",
    "custom_exception_handler",
]
