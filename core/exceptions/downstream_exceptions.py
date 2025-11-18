"""Custom exceptions for downstream service communication."""


class DownstreamServiceError(Exception):
    """Base exception for downstream service errors."""

    def __init__(
        self,
        message: str,
        service_name: str | None = None,
        status_code: int | None = None,
    ):
        """Initialize downstream service error.

        Args:
            message: Error message
            service_name: Name of the downstream service
            status_code: HTTP status code if applicable
        """
        self.service_name = service_name
        self.status_code = status_code
        super().__init__(message)


class RecipeNotFoundError(DownstreamServiceError):
    """Recipe not found in recipe-management service (404)."""

    def __init__(self, recipe_id: int):
        """Initialize recipe not found error.

        Args:
            recipe_id: ID of the recipe that was not found
        """
        self.recipe_id = recipe_id
        super().__init__(
            message=f"Recipe with ID {recipe_id} not found",
            service_name="recipe-management",
            status_code=404,
        )


class UserNotFoundError(DownstreamServiceError):
    """User not found in user-management service (404)."""

    def __init__(self, user_id: str):
        """Initialize user not found error.

        Args:
            user_id: ID of the user that was not found
        """
        self.user_id = user_id
        super().__init__(
            message=f"User with ID {user_id} not found",
            service_name="user-management",
            status_code=404,
        )


class CommentNotFoundError(DownstreamServiceError):
    """Comment not found in recipe-management service (404)."""

    def __init__(self, comment_id: int):
        """Initialize comment not found error.

        Args:
            comment_id: ID of the comment that was not found (integer)
        """
        self.comment_id = comment_id
        super().__init__(
            message=f"Comment with ID {comment_id} not found",
            service_name="recipe-management",
            status_code=404,
        )


class CollectionNotFoundError(DownstreamServiceError):
    """Collection not found in recipe-management service (404)."""

    def __init__(self, collection_id: int):
        """Initialize collection not found error.

        Args:
            collection_id: ID of the collection that was not found
        """
        self.collection_id = collection_id
        super().__init__(
            message=f"Collection with ID {collection_id} not found",
            service_name="recipe-management",
            status_code=404,
        )


class DownstreamServiceUnavailableError(DownstreamServiceError):
    """Downstream service is unavailable (500/503 errors)."""

    def __init__(self, service_name: str, status_code: int, message: str | None = None):
        """Initialize service unavailable error.

        Args:
            service_name: Name of the downstream service
            status_code: HTTP status code (500, 503, etc.)
            message: Optional custom error message
        """
        default_message = (
            f"{service_name} service is unavailable (status: {status_code})"
        )
        super().__init__(
            message=message or default_message,
            service_name=service_name,
            status_code=status_code,
        )


class ConflictError(Exception):
    """Conflict error for operations that cannot be performed (409)."""

    def __init__(self, message: str, detail: str | None = None):
        """Initialize conflict error.

        Args:
            message: Error message
            detail: Additional details about the conflict
        """
        self.detail = detail
        super().__init__(message)
