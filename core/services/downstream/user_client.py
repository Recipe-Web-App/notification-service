"""Client for user-management service."""

import structlog
from pydantic import ValidationError

from core.config.downstream_urls import USER_SERVICE_BASE_URL
from core.exceptions import UserNotFoundError
from core.schemas.user import UserProfileResponse
from core.services.downstream.base_downstream_client import (
    BaseDownstreamClient,
)

logger = structlog.get_logger(__name__)


class UserClient(BaseDownstreamClient):
    """Client for communicating with user-management service."""

    def __init__(self):
        """Initialize user client with service configuration."""
        super().__init__(
            service_name="user-management",
            base_url=USER_SERVICE_BASE_URL,
            requires_auth=True,  # Service-to-service auth for email access
        )

    def get_user(self, user_id: str) -> UserProfileResponse:
        """Fetch user profile by ID from user-management service.

        Args:
            user_id: User UUID (string format)

        Returns:
            UserProfileResponse object with user profile data including email

        Raises:
            UserNotFoundError: If user with given ID does not exist
            DownstreamServiceError: For other client errors (validation, etc.)
            DownstreamServiceUnavailableError: If service is unavailable
            requests.Timeout: If request times out
            requests.ConnectionError: If connection fails
        """
        url = f"{self.base_url}/user-management/users/{user_id}/profile"

        logger.info(
            "Fetching user profile from user-management service", user_id=user_id
        )

        response = self._make_request("GET", url)

        # Handle 404 - user not found
        if response.status_code == 404:
            logger.warning("User not found", user_id=user_id)
            raise UserNotFoundError(user_id=user_id)

        # Parse and validate response
        try:
            user_data = response.json()
            user_result = UserProfileResponse(**user_data)
            logger.info(
                "Successfully fetched user profile",
                user_id=user_id,
                username=user_result.username,
                has_email=user_result.email is not None,
            )
            return user_result

        except ValidationError as e:
            logger.error(
                "Failed to validate user profile response",
                user_id=user_id,
                validation_errors=e.errors(),
            )
            raise

        except Exception as e:
            logger.error(
                "Failed to parse user profile response",
                user_id=user_id,
                error=str(e),
            )
            raise

    def validate_follower_relationship(
        self, follower_id: str, followee_id: str
    ) -> bool:
        """Validate if a follower relationship exists between two users.

        Args:
            follower_id: UUID of the user who is following (string format)
            followee_id: UUID of the user being followed (string format)

        Returns:
            True if follower_id follows followee_id, False otherwise

        Raises:
            DownstreamServiceUnavailableError: If service is unavailable
            requests.Timeout: If request times out
            requests.ConnectionError: If connection fails
        """
        url = (
            f"{self.base_url}/user-management/users/"
            f"{follower_id}/following/{followee_id}"
        )

        logger.info(
            "Validating follower relationship",
            follower_id=follower_id,
            followee_id=followee_id,
        )

        try:
            response = self._make_request("GET", url)

            # Handle 404 - user not found
            if response.status_code == 404:
                logger.info(
                    "User not found when checking follower relationship",
                    follower_id=follower_id,
                    followee_id=followee_id,
                )
                return False

            # Parse the FollowRelationshipResponse
            if response.status_code == 200:
                data = response.json()
                is_following: bool = bool(data.get("isFollowing", False))
                logger.info(
                    "Follower relationship check completed",
                    follower_id=follower_id,
                    followee_id=followee_id,
                    is_following=is_following,
                )
                return is_following

            # For any other status code, return False
            logger.warning(
                "Unexpected status code when validating follower relationship",
                follower_id=follower_id,
                followee_id=followee_id,
                status_code=response.status_code,
            )
            return False

        except Exception as e:
            logger.error(
                "Failed to validate follower relationship",
                follower_id=follower_id,
                followee_id=followee_id,
                error=str(e),
            )
            # If the service is unavailable or errors, we should fail closed
            # and deny the relationship
            return False


# Global service instance
user_client = UserClient()
