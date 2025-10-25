"""Component tests for health check endpoint.

This module tests the health check endpoint through the full Django
request/response cycle, including URL routing and HTTP handling.
"""

from django.test import Client, TestCase


class TestHealthCheckEndpointIntegration(TestCase):
    """Component tests for health check endpoint through HTTP."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.health_url = "/health/"

    def test_health_endpoint_returns_200(self):
        """Test that GET request to /health/ returns HTTP 200."""
        response = self.client.get(self.health_url)
        self.assertEqual(response.status_code, 200)
