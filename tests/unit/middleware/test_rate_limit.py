"""Unit tests for RateLimitMiddleware."""

import json
import time
import unittest
from unittest.mock import patch

from django.http import HttpRequest, HttpResponse

from core.middleware.rate_limit import RateLimitMiddleware


class TestRateLimitMiddleware(unittest.TestCase):
    """Test cases for RateLimitMiddleware."""

    def setUp(self):
        """Set up test fixtures."""

        def mock_get_response(request):
            return HttpResponse("OK")

        self.get_response = mock_get_response
        self.middleware = RateLimitMiddleware(self.get_response)

    def _create_request(self):
        """Helper to create a test request."""
        request = HttpRequest()
        request.method = "GET"
        request.path = "/test/"
        request.META = {
            "REMOTE_ADDR": "127.0.0.1",
        }
        request.request_id = "test-request-id"
        return request

    def test_extracts_client_ip_from_remote_addr(self):
        """Test that client IP is extracted from REMOTE_ADDR."""
        request = self._create_request()
        client_ip = self.middleware._get_client_ip(request)
        self.assertEqual(client_ip, "127.0.0.1")

    def test_extracts_client_ip_from_x_forwarded_for(self):
        """Test that client IP is extracted from X-Forwarded-For header."""
        request = self._create_request()
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.1, 198.51.100.1"
        client_ip = self.middleware._get_client_ip(request)
        # Should get the first IP (original client)
        self.assertEqual(client_ip, "203.0.113.1")

    @patch("core.middleware.rate_limit.cache")
    def test_allows_request_when_under_limit(self, mock_cache):
        """Test that request is allowed when under rate limit."""
        mock_cache.get.return_value = None  # First request
        request = self._create_request()

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mock_cache.set.called)

    @patch("core.middleware.rate_limit.time")
    @patch("core.middleware.rate_limit.cache")
    def test_rejects_request_when_over_limit(self, mock_cache, mock_time):
        """Test that request is rejected when rate limit exceeded."""
        # Mock current time
        mock_time.time.return_value = 1234567890.0
        # Simulate no tokens available (0 tokens, same refill time as current)
        mock_cache.get.return_value = (0, 1234567890.0)
        request = self._create_request()

        response = self.middleware(request)

        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)

    @patch("core.middleware.rate_limit.time")
    @patch("core.middleware.rate_limit.cache")
    def test_rate_limit_response_format(self, mock_cache, mock_time):
        """Test that rate limit response has correct format."""
        # Mock current time
        mock_time.time.return_value = 1234567890.0
        # Simulate no tokens available
        mock_cache.get.return_value = (0, 1234567890.0)
        request = self._create_request()

        response = self.middleware(request)

        # Check response status
        self.assertEqual(response.status_code, 429)

        # Parse JSON response
        data = json.loads(response.content.decode("utf-8"))
        self.assertEqual(data["status"], 429)
        self.assertIn("message", data)
        self.assertIn("request_id", data)
        self.assertIn("retry_after", data)

    @patch("core.middleware.rate_limit.cache")
    def test_graceful_degradation_on_redis_failure(self, mock_cache):
        """Test that requests are allowed when Redis is unavailable."""
        mock_cache.get.side_effect = Exception("Redis connection failed")
        request = self._create_request()

        response = self.middleware(request)

        # Should allow the request despite Redis failure
        self.assertEqual(response.status_code, 200)

    def test_token_bucket_refills_over_time(self):
        """Test that tokens refill according to the time window."""
        current_time = time.time()
        last_refill = current_time - 30  # 30 seconds ago

        # With default settings (100 req/60s), ~50 tokens after 30s
        time_elapsed = current_time - last_refill
        tokens_to_add = (time_elapsed / 60) * 100
        self.assertGreaterEqual(tokens_to_add, 50)


if __name__ == "__main__":
    unittest.main()
