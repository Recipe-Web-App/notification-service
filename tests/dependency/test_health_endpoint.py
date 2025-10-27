"""Dependency tests for health check endpoints.

This module tests the health check endpoints with actual HTTP requests
to verify external dependencies and integration points.
"""

from django.test import LiveServerTestCase

import requests


class TestHealthCheckEndpointDependency(LiveServerTestCase):
    """Dependency tests for health check endpoints with real HTTP requests."""

    def test_health_endpoint_responds_to_http_request(self):
        """Test that health endpoint responds to actual HTTP request."""
        response = requests.get(f"{self.live_server_url}/api/v1/notification/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_liveness_endpoint_responds_to_http_request(self):
        """Test that liveness endpoint responds to actual HTTP request."""
        response = requests.get(
            f"{self.live_server_url}/api/v1/notification/health/live"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "alive"})

    def test_readiness_endpoint_responds_to_http_request(self):
        """Test that readiness endpoint responds to actual HTTP request."""
        response = requests.get(
            f"{self.live_server_url}/api/v1/notification/health/ready"
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        # Should be either ready or degraded, but always return 200
        self.assertIn(data["status"], ["ready", "degraded"])
        self.assertTrue(data["ready"])
        self.assertIn("dependencies", data)
        self.assertIn("database", data["dependencies"])
