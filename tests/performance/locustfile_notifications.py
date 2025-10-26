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
    """Simulates users checking the health endpoints."""

    @task(3)
    def check_health(self):
        """Load test the health check endpoint."""
        self.client.get("/api/v1/notification/health/")

    @task(2)
    def check_liveness(self):
        """Load test the liveness check endpoint."""
        self.client.get("/api/v1/notification/health/live")

    @task(1)
    def check_readiness(self):
        """Load test the readiness check endpoint."""
        self.client.get("/api/v1/notification/health/ready")
