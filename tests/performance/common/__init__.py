"""Common utilities for performance tests."""

from locust import HttpUser, between


class BasePerformanceUser(HttpUser):
    """Base class for performance test users."""

    wait_time = between(1, 3)
    token = None

    def on_start(self):
        """Called when user starts."""
        self.token = self._get_test_token()

    def _get_test_token(self):
        """Get authentication token for testing."""
        # Implement based on your auth setup
        return "test-token"
