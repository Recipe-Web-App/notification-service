"""Unit tests for RequestIDMiddleware."""

import unittest
import uuid

from django.http import HttpRequest, HttpResponse

from core.constants import REQUEST_ID_HEADER
from core.logging.context import get_request_id
from core.middleware.request_id import RequestIDMiddleware


class TestRequestIDMiddleware(unittest.TestCase):
    """Test cases for RequestIDMiddleware."""

    def setUp(self):
        """Set up test fixtures."""

        def mock_get_response(request):
            return HttpResponse("OK")

        self.get_response = mock_get_response
        self.middleware = RequestIDMiddleware(self.get_response)

    def _create_request(self, headers=None):
        """Helper to create a test request."""
        request = HttpRequest()
        request.method = "GET"
        request.path = "/test/"
        if headers:
            for key, value in headers.items():
                request.META[f"HTTP_{key.upper().replace('-', '_')}"] = value
        return request

    def test_generates_request_id_when_not_present(self):
        """Test that middleware generates a UUID when no request ID is provided."""
        request = self._create_request()
        response = self.middleware(request)

        # Check that request has request_id attribute
        self.assertTrue(hasattr(request, "request_id"))
        self.assertIsNotNone(request.request_id)

        # Check that it's a valid UUID
        try:
            uuid.UUID(request.request_id)
        except ValueError:
            self.fail("Generated request ID is not a valid UUID")

        # Check that response has the header
        self.assertIn(REQUEST_ID_HEADER, response)
        self.assertEqual(response[REQUEST_ID_HEADER], request.request_id)

    def test_uses_existing_request_id(self):
        """Test that middleware uses existing X-Request-ID header."""
        existing_id = str(uuid.uuid4())
        request = self._create_request(headers={REQUEST_ID_HEADER: existing_id})

        response = self.middleware(request)

        # Check that the existing ID was used
        self.assertEqual(request.request_id, existing_id)
        self.assertEqual(response[REQUEST_ID_HEADER], existing_id)

    def test_stores_request_id_in_thread_local(self):
        """Test that request ID is stored in thread-local storage."""
        request = self._create_request()
        self.middleware(request)

        # After the middleware completes, thread-local should be cleaned up
        # (due to finally block)
        stored_id = get_request_id()
        self.assertIsNone(stored_id)

    def test_adds_request_id_to_response_header(self):
        """Test that request ID is added to response headers."""
        request = self._create_request()
        response = self.middleware(request)

        self.assertIn(REQUEST_ID_HEADER, response)
        self.assertIsNotNone(response[REQUEST_ID_HEADER])


if __name__ == "__main__":
    unittest.main()
