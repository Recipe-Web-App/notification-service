"""Rate limiting middleware using Redis token bucket algorithm."""

import logging
import time
from collections.abc import Callable

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, JsonResponse

from core.constants import DEFAULT_RATE_LIMIT_REQUESTS, DEFAULT_RATE_LIMIT_WINDOW

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    """Middleware to enforce rate limiting using Redis token bucket algorithm.

    This middleware implements distributed rate limiting across multiple
    service instances using Redis as the backing store. It uses a token
    bucket algorithm to allow bursts while enforcing average rate limits.

    Rate limits are applied per client IP address.

    If Redis is unavailable, the middleware logs a warning and allows
    the request to proceed (graceful degradation).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Initialize the middleware.

        Args:
            get_response: The next middleware or view in the chain.
        """
        self.get_response = get_response
        self.max_requests = getattr(
            settings, "RATE_LIMIT_REQUESTS", DEFAULT_RATE_LIMIT_REQUESTS
        )
        self.window = getattr(settings, "RATE_LIMIT_WINDOW", DEFAULT_RATE_LIMIT_WINDOW)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Process the request and enforce rate limiting.

        Args:
            request: The incoming HTTP request.

        Returns:
            The HTTP response, or a 429 response if rate limit exceeded.
        """
        # Get client identifier (IP address)
        client_ip = self._get_client_ip(request)

        # Check rate limit
        allowed, retry_after = self._check_rate_limit(client_ip)

        if not allowed:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JsonResponse(
                {
                    "status": 429,
                    "message": "Rate limit exceeded. Please try again later.",
                    "request_id": getattr(request, "request_id", None),
                    "retry_after": retry_after,
                },
                status=429,
                headers={"Retry-After": str(retry_after)},
            )

        # Process the request
        return self.get_response(request)

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Extract the client IP address from the request.

        Checks X-Forwarded-For header for proxied requests, falls back to REMOTE_ADDR.

        Args:
            request: The HTTP request.

        Returns:
            The client IP address.
        """
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            # Get the first IP in the chain (the original client)
            return x_forwarded_for.split(",")[0].strip()
        return str(request.META.get("REMOTE_ADDR", "unknown"))

    def _check_rate_limit(self, client_ip: str) -> tuple[bool, int]:
        """Check if the client has exceeded the rate limit.

        Uses token bucket algorithm:
        - Each client gets a bucket with max_requests tokens
        - Tokens refill at a rate of max_requests per window
        - Each request consumes one token
        - If no tokens available, request is rejected

        Args:
            client_ip: The client IP address.

        Returns:
            Tuple of (allowed, retry_after_seconds).
            allowed is True if the request should be processed.
            retry_after_seconds indicates when to retry if rate limited.
        """
        cache_key = f"rate_limit:{client_ip}"

        try:
            # Get current token count and last refill time
            rate_limit_data = cache.get(cache_key)

            current_time = time.time()

            if rate_limit_data is None:
                # First request from this client
                tokens = self.max_requests - 1
                last_refill = current_time
            else:
                tokens, last_refill = rate_limit_data

                # Calculate tokens to add based on time elapsed
                time_elapsed = current_time - last_refill
                tokens_to_add = (time_elapsed / self.window) * self.max_requests
                tokens = min(self.max_requests, tokens + tokens_to_add)

                # Check if we have tokens available
                if tokens < 1:
                    # Calculate retry after time
                    tokens_needed = 1 - tokens
                    retry_after = int((tokens_needed / self.max_requests) * self.window)
                    return False, max(1, retry_after)

                # Consume one token
                tokens -= 1
                last_refill = current_time

            # Store updated token count
            cache.set(cache_key, (tokens, last_refill), timeout=self.window * 2)

            return True, 0

        except Exception as e:
            # If Redis is unavailable, log and allow the request (graceful degradation)
            logger.error(f"Rate limit check failed for {client_ip}: {e}")
            return True, 0
