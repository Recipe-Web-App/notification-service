"""Unit tests for core.views module."""

import unittest
from unittest.mock import Mock

from rest_framework import status

from core.views import HealthCheckView, LivenessCheckView, ReadinessCheckView


class TestHealthCheckView(unittest.TestCase):
    """Tests for HealthCheckView."""

    def test_get_returns_ok_status_and_200(self):
        """Test that GET returns {"status": "ok"} with 200 status code."""
        view = HealthCheckView()
        mock_request = Mock()

        response = view.get(mock_request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"status": "ok"})


class TestLivenessCheckView(unittest.TestCase):
    """Tests for LivenessCheckView."""

    def test_get_returns_alive_status_and_200(self):
        """Test that GET returns {"status": "alive"} with 200 status code."""
        view = LivenessCheckView()
        mock_request = Mock()

        response = view.get(mock_request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"status": "alive"})


class TestReadinessCheckView(unittest.TestCase):
    """Tests for ReadinessCheckView."""

    def test_get_returns_ready_status_and_200(self):
        """Test that GET returns {"status": "ready"} with 200 status code."""
        view = ReadinessCheckView()
        mock_request = Mock()

        response = view.get(mock_request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"status": "ready"})


if __name__ == "__main__":
    unittest.main()
