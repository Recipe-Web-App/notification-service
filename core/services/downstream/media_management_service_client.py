"""Client for media-management service."""

import structlog

from core.config.downstream_urls import MEDIA_MANAGEMENT_SERVICE_BASE_URL
from core.services.downstream.base_downstream_client import BaseDownstreamClient

logger = structlog.get_logger(__name__)


class MediaManagementServiceClient(BaseDownstreamClient):
    """Client for communicating with media-management service."""

    def __init__(self):
        """Initialize media management service client with service configuration."""
        super().__init__(
            service_name="media-management",
            base_url=MEDIA_MANAGEMENT_SERVICE_BASE_URL,
            requires_auth=True,
        )

    def get_recipe_media_ids(self, recipe_id: int) -> list[int]:
        """Fetch media IDs associated with a recipe.

        Args:
            recipe_id: Unique recipe identifier

        Returns:
            List of media IDs for the recipe (empty list if none found or
            service unavailable)

        Note:
            This method gracefully degrades - if the media service is unavailable
            or returns an error, it logs the issue and returns an empty list
            to avoid blocking notification delivery.
        """
        url = f"{self.base_url}/media/recipe/{recipe_id}"

        logger.info(
            "Fetching recipe media IDs from media-management service",
            recipe_id=recipe_id,
        )

        try:
            response = self._make_request("GET", url)

            # Handle various status codes
            if response.status_code == 200:
                media_ids = response.json()
                if isinstance(media_ids, list):
                    logger.info(
                        "Successfully fetched recipe media IDs",
                        recipe_id=recipe_id,
                        media_count=len(media_ids),
                    )
                    return media_ids
                else:
                    logger.warning(
                        "Unexpected response format from media service",
                        recipe_id=recipe_id,
                        response_type=type(media_ids).__name__,
                    )
                    return []

            elif response.status_code == 404:
                logger.info(
                    "No media found for recipe",
                    recipe_id=recipe_id,
                )
                return []

            else:
                logger.warning(
                    "Unexpected status code from media service",
                    recipe_id=recipe_id,
                    status_code=response.status_code,
                )
                return []

        except Exception as e:
            # Graceful degradation: log error but don't fail the notification
            logger.warning(
                "Failed to fetch recipe media IDs, continuing without images",
                recipe_id=recipe_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            return []

    def construct_media_download_url(self, media_id: int) -> str:
        """Construct download URL for a media file.

        Args:
            media_id: Unique media identifier

        Returns:
            Full URL to download the media file
        """
        return f"{self.base_url}/media/{media_id}/download"


# Global service instance
media_management_service_client = MediaManagementServiceClient()
