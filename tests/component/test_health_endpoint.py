"""Component tests for health check endpoints.

This module tests the health check endpoints through the full Django
request/response cycle, including URL routing and HTTP handling.
"""

from django.test import Client, TestCase


class TestHealthCheckEndpointIntegration(TestCase):
    """Component tests for health check endpoints through HTTP."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()

    def test_health_endpoint_returns_200_and_ok_status(self):
        """Test that GET request to /health/ returns HTTP 200 with ok status."""
        response = self.client.get("/api/v1/notification/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_liveness_endpoint_returns_200_and_alive_status(self):
        """Test that GET request to /health/live returns HTTP 200 with alive status."""
        response = self.client.get("/api/v1/notification/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "alive"})

    def test_readiness_endpoint_returns_200_and_ready_status(self):
        """Test that GET request to /health/ready returns HTTP 200 with ready status."""
        response = self.client.get("/api/v1/notification/health/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ready"})
