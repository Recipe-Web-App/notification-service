"""Unit tests for ProcessTimeMiddleware."""

import time
import unittest

from django.http import HttpRequest, HttpResponse

from core.constants import PROCESS_TIME_HEADER
from core.middleware.process_time import ProcessTimeMiddleware


class TestProcessTimeMiddleware(unittest.TestCase):
    """Test cases for ProcessTimeMiddleware."""

    def setUp(self):
        """Set up test fixtures."""

        def mock_get_response(request):
            return HttpResponse("OK")

        self.get_response = mock_get_response
        self.middleware = ProcessTimeMiddleware(self.get_response)

    def _create_slow_middleware(self):
        """Create middleware with slow response."""

        def slow_get_response(request):
            time.sleep(0.1)  # Sleep for 100ms
            return HttpResponse("OK")

        return ProcessTimeMiddleware(slow_get_response)

    def _create_request(self):
        """Helper to create a test request."""
        request = HttpRequest()
        request.method = "GET"
        request.path = "/test/"
        return request

    def test_adds_process_time_header(self):
        """Test that process time header is added to response."""
        request = self._create_request()
        response = self.middleware(request)

        self.assertIn(PROCESS_TIME_HEADER, response)
        self.assertIsNotNone(response[PROCESS_TIME_HEADER])

    def test_process_time_is_numeric(self):
        """Test that process time value is a valid number."""
        request = self._create_request()
        response = self.middleware(request)

        process_time = response[PROCESS_TIME_HEADER]
        try:
            float(process_time)
        except ValueError:
            self.fail(f"Process time '{process_time}' is not a valid number")

    def test_process_time_is_positive(self):
        """Test that process time is a positive value."""
        request = self._create_request()
        response = self.middleware(request)

        process_time = float(response[PROCESS_TIME_HEADER])
        self.assertGreaterEqual(process_time, 0)

    def test_process_time_measures_duration(self):
        """Test that process time accurately measures request duration."""
        slow_middleware = self._create_slow_middleware()
        request = self._create_request()
        response = slow_middleware(request)

        process_time = float(response[PROCESS_TIME_HEADER])
        # Should be at least 0.1 seconds (100ms) since we slept
        self.assertGreaterEqual(process_time, 0.1)

    def test_process_time_format(self):
        """Test that process time is formatted with proper precision."""
        request = self._create_request()
        response = self.middleware(request)

        process_time = response[PROCESS_TIME_HEADER]
        # Should have decimal places (checking for '.' in the string)
        self.assertIn(".", process_time)


if __name__ == "__main__":
    unittest.main()
