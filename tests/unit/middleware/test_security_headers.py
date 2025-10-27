"""Unit tests for SecurityHeadersMiddleware."""

import unittest

from django.http import HttpRequest, HttpResponse

from core.constants import SECURITY_HEADERS
from core.middleware.security_headers import SecurityHeadersMiddleware


class TestSecurityHeadersMiddleware(unittest.TestCase):
    """Test cases for SecurityHeadersMiddleware."""

    def setUp(self):
        """Set up test fixtures."""

        def mock_get_response(request):
            return HttpResponse("OK")

        self.get_response = mock_get_response
        self.middleware = SecurityHeadersMiddleware(self.get_response)

    def _create_request(self):
        """Helper to create a test request."""
        request = HttpRequest()
        request.method = "GET"
        request.path = "/test/"
        return request

    def test_adds_all_security_headers(self):
        """Test that all security headers are added to the response."""
        request = self._create_request()
        response = self.middleware(request)

        for header, value in SECURITY_HEADERS.items():
            self.assertIn(header, response)
            self.assertEqual(response[header], value)

    def test_x_frame_options_header(self):
        """Test that X-Frame-Options header is set correctly."""
        request = self._create_request()
        response = self.middleware(request)
        self.assertEqual(response["X-Frame-Options"], "DENY")

    def test_x_content_type_options_header(self):
        """Test that X-Content-Type-Options header is set correctly."""
        request = self._create_request()
        response = self.middleware(request)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

    def test_x_xss_protection_header(self):
        """Test that X-XSS-Protection header is set correctly."""
        request = self._create_request()
        response = self.middleware(request)
        self.assertEqual(response["X-XSS-Protection"], "1; mode=block")

    def test_strict_transport_security_header(self):
        """Test that Strict-Transport-Security header is set correctly."""
        request = self._create_request()
        response = self.middleware(request)
        self.assertEqual(
            response["Strict-Transport-Security"],
            "max-age=31536000; includeSubDomains",
        )

    def test_referrer_policy_header(self):
        """Test that Referrer-Policy header is set correctly."""
        request = self._create_request()
        response = self.middleware(request)
        self.assertEqual(response["Referrer-Policy"], "strict-origin-when-cross-origin")

    def test_content_security_policy_header(self):
        """Test that Content-Security-Policy header is set correctly."""
        request = self._create_request()
        response = self.middleware(request)
        self.assertEqual(response["Content-Security-Policy"], "default-src 'self'")


if __name__ == "__main__":
    unittest.main()
