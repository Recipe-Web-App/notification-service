"""OAuth2 authentication backend for Django REST Framework.

Supports two validation modes:
1. Token Introspection: Validates tokens by calling auth-service (recommended)
2. Local JWT Validation: Validates JWT signatures locally using shared secret
"""

from typing import Any, cast

from django.conf import settings
from django.core.cache import cache

import jwt
import requests
import structlog
from rest_framework import authentication, exceptions

logger = structlog.get_logger(__name__)


class OAuth2User:
    """Simple user object for OAuth2 authenticated requests.

    This is not a Django User model, just a container for token claims.
    """

    def __init__(self, user_id: str, client_id: str, scopes: list[str]):
        """Initialize OAuth2 user.

        Args:
            user_id: User ID from token (or client_id for client_credentials)
            client_id: OAuth2 client ID
            scopes: List of granted scopes
        """
        self.id = user_id
        self.user_id = user_id
        self.client_id = client_id
        self.scopes = scopes
        self.is_authenticated = True

    def has_scope(self, scope: str) -> bool:
        """Check if user has a specific scope.

        Args:
            scope: Scope to check

        Returns:
            True if user has the scope
        """
        return scope in self.scopes

    def __str__(self):
        """String representation."""
        return f"OAuth2User(user_id={self.user_id}, client_id={self.client_id})"


class OAuth2Authentication(authentication.BaseAuthentication):
    """OAuth2 Bearer token authentication.

    Extracts and validates Bearer tokens from Authorization header.
    Supports both introspection and local JWT validation.
    """

    def authenticate(self, request):
        """Authenticate the request using OAuth2 Bearer token.

        Args:
            request: Django request object

        Returns:
            Tuple of (user, auth) or None if authentication not attempted

        Raises:
            AuthenticationFailed: If authentication fails
        """
        # Skip authentication if OAuth2 is disabled
        if not settings.OAUTH2_SERVICE_ENABLED:
            return None

        # Extract token from Authorization header
        auth_header = request.headers.get("authorization")
        if not auth_header:
            return None  # No authentication attempted

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise exceptions.AuthenticationFailed("Invalid authorization header format")

        token = parts[1]

        # Validate token using configured method
        if settings.OAUTH2_INTROSPECTION_ENABLED:
            token_data = self._validate_via_introspection(token)
        else:
            token_data = self._validate_via_jwt(token)

        # Create user object from token data
        user = OAuth2User(
            user_id=token_data.get("sub", token_data.get("client_id", "unknown")),
            client_id=token_data.get("client_id", "unknown"),
            scopes=token_data.get("scopes", []),
        )

        return (user, token)

    def _validate_via_introspection(self, token: str) -> dict[str, Any]:
        """Validate token via auth-service introspection endpoint.

        Args:
            token: Access token to validate

        Returns:
            Token data from introspection

        Raises:
            AuthenticationFailed: If token is invalid
        """
        # Check cache first
        cache_key = f"{settings.OAUTH2_TOKEN_CACHE_PREFIX}{token[:16]}"
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.debug("Using cached token introspection result")
            return cast("dict[str, Any]", cached_data)

        # Call introspection endpoint
        try:
            logger.debug("Calling token introspection endpoint")
            response = requests.post(
                settings.OAUTH2_INTROSPECT_URL,
                data={
                    "token": token,
                    "token_type_hint": "access_token",
                },
                auth=(settings.OAUTH2_CLIENT_ID, settings.OAUTH2_CLIENT_SECRET),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=5,
            )

            if response.status_code != 200:
                logger.warning(
                    "Token introspection failed",
                    status_code=response.status_code,
                )
                raise exceptions.AuthenticationFailed("Token introspection failed")

            data = response.json()

            # Check if token is active
            if not data.get("active", False):
                logger.info("Token is not active")
                raise exceptions.AuthenticationFailed("Token is not active")

            # Cache the result
            cache.set(cache_key, data, timeout=settings.OAUTH2_TOKEN_CACHE_TTL)

            return cast("dict[str, Any]", data)

        except requests.RequestException as e:
            logger.error("Token introspection request failed", error=str(e))
            raise exceptions.AuthenticationFailed(
                "Token validation service unavailable"
            ) from e

    def _validate_via_jwt(self, token: str) -> dict[str, Any]:
        """Validate token locally by verifying JWT signature.

        Args:
            token: JWT access token to validate

        Returns:
            Token claims/payload

        Raises:
            AuthenticationFailed: If token is invalid
        """
        if not settings.JWT_SECRET:
            logger.error("JWT_SECRET not configured but local validation is enabled")
            raise exceptions.AuthenticationFailed("JWT validation not configured")

        try:
            # Decode and verify JWT
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=["HS256", "HS384", "HS512"],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_nbf": True,
                },
            )

            # Verify token type
            token_type = payload.get("type")
            if token_type != "access_token":
                logger.warning("Invalid token type", token_type=token_type)
                raise exceptions.AuthenticationFailed(
                    f"Invalid token type: {token_type}"
                )

            # Return payload with standardized field names
            return {
                "active": True,
                "sub": payload.get("sub"),
                "client_id": payload.get("client_id"),
                "scopes": payload.get("scopes", []),
                "user_id": payload.get("user_id"),
                "exp": payload.get("exp"),
                "iat": payload.get("iat"),
            }

        except jwt.ExpiredSignatureError as e:
            logger.info("JWT token has expired")
            raise exceptions.AuthenticationFailed("Token has expired") from e
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid JWT token", error=str(e))
            raise exceptions.AuthenticationFailed("Invalid token") from e
        except Exception as e:
            logger.error("JWT validation failed", error=str(e))
            raise exceptions.AuthenticationFailed("Token validation failed") from e

    def authenticate_header(self, _request):
        """Return WWW-Authenticate header value for 401 responses.

        Args:
            _request: Django request object (unused)

        Returns:
            Authentication header value
        """
        return "Bearer"
