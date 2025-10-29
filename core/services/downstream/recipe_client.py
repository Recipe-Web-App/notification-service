"""Client for recipe-management service."""

import structlog
from pydantic import ValidationError

from core.config.downstream_urls import RECIPE_SERVICE_BASE_URL
from core.exceptions import RecipeNotFoundError
from core.schemas.recipe import RecipeDto
from core.services.downstream.base_downstream_client import BaseDownstreamClient

logger = structlog.get_logger(__name__)


class RecipeClient(BaseDownstreamClient):
    """Client for communicating with recipe-management service."""

    def __init__(self):
        """Initialize recipe client with service configuration."""
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


# Global service instance
recipe_client = RecipeClient()
