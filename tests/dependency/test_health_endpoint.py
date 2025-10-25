"""Dependency tests for health check endpoint.

This module tests the health check endpoint with actual HTTP requests
to verify external dependencies and integration points.
"""

from django.test import LiveServerTestCase

import requests


class TestHealthCheckEndpointDependency(LiveServerTestCase):
    """Dependency tests for health check endpoint with real HTTP requests."""

    def test_health_endpoint_responds_to_http_request(self):
        """Test that health endpoint responds to actual HTTP request."""
        response = requests.get(f"{self.live_server_url}/health/")
        self.assertEqual(response.status_code, 200)
