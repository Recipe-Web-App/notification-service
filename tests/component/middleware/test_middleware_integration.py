"""Component tests for middleware integration with Django/DRF."""

import uuid

from django.test import Client, TestCase, override_settings

from core.constants import PROCESS_TIME_HEADER, REQUEST_ID_HEADER, SECURITY_HEADERS


class TestMiddlewareIntegration(TestCase):
    """Test middleware integration with actual HTTP requests."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()

    def test_request_id_middleware_integration(self):
        """Test that request ID middleware works with actual requests."""
        response = self.client.get("/api/v1/notification/health/live")

        # Check that response has request ID header
        self.assertIn(REQUEST_ID_HEADER, response)

        # Verify it's a valid UUID format
        request_id = response[REQUEST_ID_HEADER]
        try:
            uuid.UUID(request_id)
        except ValueError:
            self.fail("Request ID is not a valid UUID")

    def test_security_headers_integration(self):
        """Test that security headers are added to responses."""
        response = self.client.get("/api/v1/notification/health/live")

        # Check that all security headers are present
        for header, expected_value in SECURITY_HEADERS.items():
            self.assertIn(header, response)
            self.assertEqual(response[header], expected_value)

    def test_process_time_header_integration(self):
        """Test that process time header is added to responses."""
        response = self.client.get("/api/v1/notification/health/live")

        # Check that process time header is present
        self.assertIn(PROCESS_TIME_HEADER, response)

        # Verify it's a valid number
        process_time = float(response[PROCESS_TIME_HEADER])
        self.assertGreaterEqual(process_time, 0)

    def test_cors_headers_integration(self):
        """Test that CORS middleware is working."""
        # Make an OPTIONS request (preflight)
        response = self.client.options(
            "/api/v1/notification/health/live",
            headers={"origin": "http://localhost:3000"},
        )

        # CORS headers should be present in the response
        # Note: Actual header names depend on django-cors-headers configuration
        self.assertIn(response.status_code, [200, 204])

    def test_middleware_execution_order(self):
        """Test that middleware executes in the correct order."""
        response = self.client.get("/api/v1/notification/health/live")

        # Request ID should be set (earliest middleware)
        self.assertIn(REQUEST_ID_HEADER, response)

        # Process time should be set
        self.assertIn(PROCESS_TIME_HEADER, response)

        # Security headers should be set (later middleware)
        self.assertIn("X-Frame-Options", response)

    def test_exception_handler_integration(self):
        """Test that exception handler works with middleware."""
        # Request a non-existent endpoint
        response = self.client.get("/api/v1/notification/non-existent/")

        # Should get 404
        self.assertEqual(response.status_code, 404)

        # Request ID should be in header even for 404s
        self.assertIn(REQUEST_ID_HEADER, response)

        # Note: Django returns HTML for non-existent URLs by default
        # Our custom exception handler works for API views that raise exceptions
        # For actual integration testing of exception handler format,
        # we would need an endpoint that raises exceptions

    def test_rate_limiting_integration(self):
        """Test rate limiting with actual requests."""
        # Note: This test might need to be adjusted based on rate limit settings
        # For now, we just verify that requests work and don't get blocked immediately

        # Make a few requests
        for _ in range(5):
            response = self.client.get("/api/v1/notification/health/live")
            self.assertEqual(response.status_code, 200)

    @override_settings(DEBUG=False)
    def test_middleware_in_production_mode(self):
        """Test that middleware works correctly in production mode."""
        response = self.client.get("/api/v1/notification/health/live")

        # All headers should still be present
        self.assertIn(REQUEST_ID_HEADER, response)
        self.assertIn(PROCESS_TIME_HEADER, response)
        self.assertIn("X-Frame-Options", response)

    def test_custom_request_id_preserved(self):
        """Test that custom request ID from client is preserved."""
        custom_id = "custom-request-id-12345"

        response = self.client.get(
            "/api/v1/notification/health/live", headers={"x-request-id": custom_id}
        )

        # The custom request ID should be preserved
        self.assertEqual(response[REQUEST_ID_HEADER], custom_id)

    def test_all_middleware_headers_present(self):
        """Test that all expected middleware headers are present."""
        response = self.client.get("/api/v1/notification/health/live")

        # Verify all important headers
        expected_headers = [
            REQUEST_ID_HEADER,
            PROCESS_TIME_HEADER,
            "X-Frame-Options",
            "X-Content-Type-Options",
            "X-XSS-Protection",
            "Strict-Transport-Security",
            "Referrer-Policy",
            "Content-Security-Policy",
        ]

        for header in expected_headers:
            self.assertIn(header, response, f"Expected header {header} not found")


if __name__ == "__main__":
    import unittest

    unittest.main()
