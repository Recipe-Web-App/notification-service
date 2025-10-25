"""Performance tests for notification service endpoints using Locust.

This module defines load testing scenarios for the notification service
to measure performance under various load conditions.

Usage:
    # Start Django server first
    poetry run local

    # In another terminal, run performance tests
    poetry run test-performance
"""

from locust import HttpUser, task


class HealthCheckUser(HttpUser):
    """Simulates users checking the health endpoint."""

    @task
    def check_health(self):
        """Load test the health check endpoint."""
        self.client.get("/health/")
