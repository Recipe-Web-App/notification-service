"""Client for recipe-management service."""

import structlog
from pydantic import ValidationError

from core.config.downstream_urls import RECIPE_SERVICE_BASE_URL
from core.exceptions import CommentNotFoundError, RecipeNotFoundError
from core.schemas.recipe import CommentDto, RecipeDto
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

    def get_comment(self, comment_id: str) -> CommentDto:
        """Fetch comment by ID from recipe-management service.

        Args:
            comment_id: Unique comment identifier (UUID)

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


# Global service instance
recipe_management_service_client = RecipeManagementServiceClient()
