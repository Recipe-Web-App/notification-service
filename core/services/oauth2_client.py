"""OAuth2 client service for service-to-service authentication.

This service handles:
- Token fetching using client_credentials flow
- Token caching with Redis
- Automatic token refresh before expiry
"""

import time

from django.conf import settings
from django.core.cache import cache

import requests
import structlog

logger = structlog.get_logger(__name__)


class OAuth2ClientError(Exception):
    """Base exception for OAuth2 client errors."""

    pass


class OAuth2TokenResponse:
    """OAuth2 token response model."""

    def __init__(self, access_token: str, expires_in: int, token_type: str = "Bearer"):
        """Initialize token response.

        Args:
            access_token: The access token
            expires_in: Token lifetime in seconds
            token_type: Token type (default: Bearer)
        """
        self.access_token = access_token
        self.expires_in = expires_in
        self.token_type = token_type
        self.issued_at = time.time()

    def is_expired(self, buffer_seconds: int = 30) -> bool:
        """Check if token is expired or will expire soon.

        Args:
            buffer_seconds: Refresh token this many seconds before expiry

        Returns:
            True if token is expired or will expire within buffer time
        """
        elapsed = time.time() - self.issued_at
        return elapsed >= (self.expires_in - buffer_seconds)


class OAuth2ClientService:
    """Service for OAuth2 client_credentials flow."""

    CACHE_KEY = "oauth2:service_token"

    def __init__(self):
        """Initialize OAuth2 client service."""
        self.client_id = settings.OAUTH2_CLIENT_ID
        self.client_secret = settings.OAUTH2_CLIENT_SECRET
        self.token_url = settings.OAUTH2_TOKEN_URL
        self.scopes = settings.OAUTH2_SCOPES
        self._cached_token: OAuth2TokenResponse | None = None

    def get_access_token(self) -> str:
        """Get a valid access token, fetching or refreshing as needed.

        Returns:
            Valid access token

        Raises:
            OAuth2ClientError: If token fetch fails
        """
        if not settings.OAUTH2_SERVICE_TO_SERVICE_ENABLED:
            raise OAuth2ClientError(
                "Service-to-service OAuth2 is disabled "
                "(OAUTH2_SERVICE_TO_SERVICE_ENABLED=false)"
            )

        if not self.client_id or not self.client_secret:
            raise OAuth2ClientError(
                "OAuth2 client credentials not configured "
                "(OAUTH2_CLIENT_ID/OAUTH2_CLIENT_SECRET missing)"
            )

        # Try to get cached token from Redis
        cached_token = self._get_cached_token()
        if cached_token and not cached_token.is_expired():
            logger.debug("Using cached OAuth2 access token")
            return cached_token.access_token

        # Fetch new token
        logger.info("Fetching new OAuth2 access token", client_id=self.client_id)
        token_response = self._fetch_token()

        # Cache the token
        self._cache_token(token_response)

        return token_response.access_token

    def _fetch_token(self) -> OAuth2TokenResponse:
        """Fetch access token from auth-service using client_credentials flow.

        Returns:
            Token response

        Raises:
            OAuth2ClientError: If token fetch fails
        """
        try:
            response = requests.post(
                self.token_url,
                data={
                    "grant_type": settings.OAUTH2_GRANT_TYPE,
                    "scope": " ".join(self.scopes),
                },
                auth=(self.client_id, self.client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )

            if response.status_code != 200:
                logger.error(
                    "OAuth2 token request failed",
                    status_code=response.status_code,
                    response=response.text,
                )
                raise OAuth2ClientError(
                    f"Token request failed with status {response.status_code}: "
                    f"{response.text}"
                )

            data = response.json()
            return OAuth2TokenResponse(
                access_token=data["access_token"],
                expires_in=data["expires_in"],
                token_type=data.get("token_type", "Bearer"),
            )

        except requests.RequestException as e:
            logger.error("OAuth2 token request exception", error=str(e))
            raise OAuth2ClientError(f"Token request failed: {e}") from e

    def _get_cached_token(self) -> OAuth2TokenResponse | None:
        """Get cached token from Redis.

        Returns:
            Cached token response or None
        """
        try:
            cached_data = cache.get(self.CACHE_KEY)
            if cached_data:
                return OAuth2TokenResponse(
                    access_token=cached_data["access_token"],
                    expires_in=cached_data["expires_in"],
                    token_type=cached_data["token_type"],
                )
        except Exception as e:
            logger.warning("Failed to retrieve cached OAuth2 token", error=str(e))

        return None

    def _cache_token(self, token: OAuth2TokenResponse) -> None:
        """Cache token in Redis.

        Args:
            token: Token response to cache
        """
        try:
            # Store token data
            cache_data = {
                "access_token": token.access_token,
                "expires_in": token.expires_in,
                "token_type": token.token_type,
            }

            # Cache for slightly less than token lifetime to ensure we refresh
            # before expiry
            cache_ttl = max(token.expires_in - 30, 60)  # At least 60 seconds

            cache.set(self.CACHE_KEY, cache_data, timeout=cache_ttl)
            logger.debug("Cached OAuth2 access token", ttl=cache_ttl)

        except Exception as e:
            logger.warning("Failed to cache OAuth2 token", error=str(e))
            # Don't fail if caching fails - token can still be used

    def clear_cache(self) -> None:
        """Clear cached token (useful for testing or forced refresh)."""
        try:
            cache.delete(self.CACHE_KEY)
            logger.debug("Cleared cached OAuth2 token")
        except Exception as e:
            logger.warning("Failed to clear cached OAuth2 token", error=str(e))


# Global service instance
oauth2_client_service = OAuth2ClientService()
