"""Base client for downstream service communication."""

from typing import Any

import requests
import structlog

from core.exceptions import DownstreamServiceError, DownstreamServiceUnavailableError
from core.services.oauth2_client import oauth2_client_service

logger = structlog.get_logger(__name__)


class BaseDownstreamClient:
    """Base class for downstream service HTTP clients."""

    def __init__(self, service_name: str, base_url: str, requires_auth: bool = True):
        """Initialize base downstream client.

        Args:
            service_name: Name of the downstream service (for logging/errors)
            base_url: Base URL for the service
            requires_auth: Whether requests require OAuth2 authentication
        """
        self.service_name = service_name
        self.base_url = base_url
        self.requires_auth = requires_auth
        self.timeout = 10  # seconds

    def _get_headers(self) -> dict[str, str]:
        """Get common HTTP headers for requests.

        Returns:
            Dictionary of headers

        Raises:
            DownstreamServiceError: If authentication is required but token fetch fails
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if self.requires_auth:
            try:
                token = oauth2_client_service.get_access_token()
                headers["Authorization"] = f"Bearer {token}"
            except Exception as e:
                logger.error(
                    "Failed to get OAuth2 token for downstream request",
                    service=self.service_name,
                    error=str(e),
                )
                raise DownstreamServiceError(
                    message=f"Failed to authenticate with {self.service_name}: {e}",
                    service_name=self.service_name,
                ) from e

        return headers

    def _make_request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        **kwargs,
    ) -> requests.Response:
        """Make HTTP request with error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL for the request
            params: Query parameters
            json_data: JSON body data
            **kwargs: Additional arguments to pass to requests

        Returns:
            Response object

        Raises:
            DownstreamServiceError: For client errors (4xx except 404)
            DownstreamServiceUnavailableError: For server errors (5xx)
            requests.Timeout: For timeout errors
            requests.ConnectionError: For connection errors
        """
        headers = self._get_headers()

        # Merge custom headers if provided
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        # Set default timeout if not provided
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout

        logger.info(
            "Making downstream service request",
            service=self.service_name,
            method=method,
            url=url,
            params=params,
        )

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data,
                **kwargs,
            )

            # Log response
            logger.info(
                "Received downstream service response",
                service=self.service_name,
                method=method,
                url=url,
                status_code=response.status_code,
            )

            # Handle error responses (except 404, which is handled by specific clients)
            if response.status_code >= 500:
                logger.error(
                    "Downstream service returned server error",
                    service=self.service_name,
                    status_code=response.status_code,
                    response_text=response.text,
                )
                raise DownstreamServiceUnavailableError(
                    service_name=self.service_name,
                    status_code=response.status_code,
                )

            if response.status_code >= 400 and response.status_code != 404:
                logger.error(
                    "Downstream service returned client error",
                    service=self.service_name,
                    status_code=response.status_code,
                    response_text=response.text,
                )
                error_msg = (
                    f"{self.service_name} returned "
                    f"{response.status_code}: {response.text}"
                )
                raise DownstreamServiceError(
                    message=error_msg,
                    service_name=self.service_name,
                    status_code=response.status_code,
                )

            return response

        except requests.Timeout:
            logger.error(
                "Downstream service request timed out",
                service=self.service_name,
                method=method,
                url=url,
                timeout=self.timeout,
            )
            raise

        except requests.ConnectionError as e:
            logger.error(
                "Failed to connect to downstream service",
                service=self.service_name,
                method=method,
                url=url,
                error=str(e),
            )
            raise
