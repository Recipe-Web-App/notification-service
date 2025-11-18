"""Client for recipe-management service."""

import structlog
from pydantic import ValidationError

from core.config.downstream_urls import RECIPE_SERVICE_BASE_URL
from core.exceptions import (
    CollectionNotFoundError,
    CommentNotFoundError,
    RecipeNotFoundError,
)
from core.schemas.recipe import CollectionDto, CommentDto, RecipeDto
from core.services.downstream.base_downstream_client import BaseDownstreamClient

logger = structlog.get_logger(__name__)


class RecipeManagementServiceClient(BaseDownstreamClient):
    """Client for communicating with recipe-management service."""

    def __init__(self):
        """Initialize recipe management service client with service configuration."""
        super().__init__(
            service_name="recipe-management",
            base_url=RECIPE_SERVICE_BASE_URL,
            requires_auth=True,
        )

    def get_recipe(self, recipe_id: int) -> RecipeDto:
        """Fetch recipe by ID from recipe-management service.

        Args:
            recipe_id: Unique recipe identifier

        Returns:
            RecipeDto object with recipe data

        Raises:
            RecipeNotFoundError: If recipe with given ID does not exist
            DownstreamServiceError: For other client errors (auth, validation, etc.)
            DownstreamServiceUnavailableError: If service is unavailable
            requests.Timeout: If request times out
            requests.ConnectionError: If connection fails
        """
        url = f"{self.base_url}/recipes/{recipe_id}"

        logger.info(
            "Fetching recipe from recipe-management service", recipe_id=recipe_id
        )

        response = self._make_request("GET", url)

        # Handle 404 - recipe not found
        if response.status_code == 404:
            logger.warning("Recipe not found", recipe_id=recipe_id)
            raise RecipeNotFoundError(recipe_id=recipe_id)

        # Parse and validate response
        try:
            recipe_data = response.json()
            recipe_dto = RecipeDto(**recipe_data)
            logger.info(
                "Successfully fetched recipe",
                recipe_id=recipe_id,
                title=recipe_dto.title,
            )
            return recipe_dto

        except ValidationError as e:
            logger.error(
                "Failed to validate recipe response",
                recipe_id=recipe_id,
                validation_errors=e.errors(),
            )
            raise

        except Exception as e:
            logger.error(
                "Failed to parse recipe response",
                recipe_id=recipe_id,
                error=str(e),
            )
            raise

    def get_comment(self, comment_id: int) -> CommentDto:
        """Fetch comment by ID from recipe-management service.

        Args:
            comment_id: Unique comment identifier (integer)

        Returns:
            CommentDto object with comment data

        Raises:
            CommentNotFoundError: If comment with given ID does not exist
            DownstreamServiceError: For other client errors (auth, validation, etc.)
            DownstreamServiceUnavailableError: If service is unavailable
            requests.Timeout: If request times out
            requests.ConnectionError: If connection fails
        """
        url = f"{self.base_url}/comments/{comment_id}"

        logger.info(
            "Fetching comment from recipe-management service", comment_id=comment_id
        )

        response = self._make_request("GET", url)

        # Handle 404 - comment not found
        if response.status_code == 404:
            logger.warning("Comment not found", comment_id=comment_id)
            raise CommentNotFoundError(comment_id=comment_id)

        # Parse and validate response
        try:
            comment_data = response.json()
            comment_dto = CommentDto(**comment_data)
            logger.info(
                "Successfully fetched comment",
                comment_id=comment_id,
                recipe_id=comment_dto.recipe_id,
            )
            return comment_dto

        except ValidationError as e:
            logger.error(
                "Failed to validate comment response",
                comment_id=comment_id,
                validation_errors=e.errors(),
            )
            raise

        except Exception as e:
            logger.error(
                "Failed to parse comment response",
                comment_id=comment_id,
                error=str(e),
            )
            raise

    def get_collection(self, collection_id: int) -> CollectionDto:
        """Fetch collection by ID from recipe-management service.

        Args:
            collection_id: Unique collection identifier

        Returns:
            CollectionDto object with collection data

        Raises:
            CollectionNotFoundError: If collection with given ID does not exist
            DownstreamServiceError: For other client errors (auth, validation, etc.)
            DownstreamServiceUnavailableError: If service is unavailable
            requests.Timeout: If request times out
            requests.ConnectionError: If connection fails
        """
        url = f"{self.base_url}/collections/{collection_id}"

        logger.info(
            "Fetching collection from recipe-management service",
            collection_id=collection_id,
        )

        response = self._make_request("GET", url)

        # Handle 404 - collection not found
        if response.status_code == 404:
            logger.warning("Collection not found", collection_id=collection_id)
            raise CollectionNotFoundError(collection_id=collection_id)

        # Parse and validate response
        try:
            collection_data = response.json()
            collection_dto = CollectionDto(**collection_data)
            logger.info(
                "Successfully fetched collection",
                collection_id=collection_id,
                name=collection_dto.name,
            )
            return collection_dto

        except ValidationError as e:
            logger.error(
                "Failed to validate collection response",
                collection_id=collection_id,
                validation_errors=e.errors(),
            )
            raise

        except Exception as e:
            logger.error(
                "Failed to parse collection response",
                collection_id=collection_id,
                error=str(e),
            )
            raise

    def get_user_recipe_count(self, user_id: str) -> int:
        """Fetch count of published recipes for a user.

        Fetches the count of published recipes for a user from the
        recipe-management service.

        Args:
            user_id: User's UUID

        Returns:
            Integer count of published recipes (0 if user has no recipes
            or doesn't exist)

        Raises:
            DownstreamServiceError: For client errors (auth, validation)
            DownstreamServiceUnavailableError: If service is unavailable
            requests.Timeout: If request times out
            requests.ConnectionError: If connection fails
        """
        url = f"{self.base_url}/recipes/count/user/{user_id}"

        logger.info(
            "Fetching user recipe count from recipe-management service", user_id=user_id
        )

        response = self._make_request("GET", url)

        # Handle 404 - user has no recipes or doesn't exist
        if response.status_code == 404:
            logger.info("User has no recipes or user not found", user_id=user_id)
            return 0

        # Parse response
        try:
            data = response.json()
            count: int = int(data.get("count", 0))
            logger.info(
                "Successfully fetched user recipe count",
                user_id=user_id,
                count=count,
            )
            return count

        except Exception as e:
            logger.error(
                "Failed to parse recipe count response",
                user_id=user_id,
                error=str(e),
            )
            # Default to 0 rather than failing the notification
            return 0


# Global service instance
recipe_management_service_client = RecipeManagementServiceClient()
