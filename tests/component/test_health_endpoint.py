"""Component tests for health check endpoints.

This module tests the health check endpoints through the full Django
request/response cycle, including URL routing and HTTP handling.
"""

from unittest.mock import patch

from django.db.utils import OperationalError
from django.test import Client, TestCase

from core.services import health_service


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

    def test_readiness_endpoint_returns_200_when_database_healthy(self):
        """Test GET /health/ready returns HTTP 200 with ready status when DB healthy."""
        response = self.client.get("/api/v1/notification/health/ready")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "ready")
        self.assertTrue(data["ready"])
        self.assertFalse(data["degraded"])
        self.assertIn("dependencies", data)
        self.assertIn("database", data["dependencies"])
        self.assertTrue(data["dependencies"]["database"]["healthy"])
        self.assertEqual(data["dependencies"]["database"]["status"], "healthy")

    @patch("core.services.health_service.connection.ensure_connection")
    def test_readiness_endpoint_returns_degraded_when_database_down(
        self, mock_ensure_connection
    ):
        """Test readiness endpoint returns HTTP 200 degraded status when DB down."""
        # Clear cache to force fresh check
        health_service._db_health_cache = None
        health_service._db_health_cache_time = 0.0

        # Simulate database being down
        mock_ensure_connection.side_effect = OperationalError("Connection refused")

        response = self.client.get("/api/v1/notification/health/ready")

        # Should still return 200 OK (not 503)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "degraded")
        self.assertTrue(data["ready"])  # Still ready to serve requests
        self.assertTrue(data["degraded"])  # But in degraded mode
        self.assertIn("dependencies", data)
        self.assertIn("database", data["dependencies"])
        self.assertFalse(data["dependencies"]["database"]["healthy"])
        self.assertEqual(data["dependencies"]["database"]["status"], "unhealthy")
        self.assertIn("Connection refused", data["dependencies"]["database"]["message"])
