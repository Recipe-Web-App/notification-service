"""Unit tests for health check endpoint.

This module tests the HealthCheckView in isolation, focusing on the view's
behavior without full HTTP request/response cycle.
"""

import json
import unittest
from unittest.mock import MagicMock, Mock

from rest_framework import status
from rest_framework.views import APIView

from core.views import HealthCheckView


class TestHealthCheckView(unittest.TestCase):
    """Unit tests for HealthCheckView class."""

    def setUp(self):
        """Set up test fixtures."""
        self.view = HealthCheckView()

    def test_view_inherits_from_apiview(self):
        """Test that HealthCheckView inherits from APIView."""
        self.assertIsInstance(self.view, APIView)

    def test_view_has_get_method(self):
        """Test that HealthCheckView has a get method."""
        self.assertTrue(hasattr(self.view, "get"))
        self.assertTrue(callable(self.view.get))

    def test_get_returns_response_object(self):
        """Test that get method returns a Response object."""
        mock_request = Mock()
        response = self.view.get(mock_request)

        # Check that response has the attributes we expect
        self.assertTrue(hasattr(response, "status_code"))
        self.assertTrue(hasattr(response, "data"))

    def test_get_returns_status_200(self):
        """Test that get method returns HTTP 200 OK."""
        mock_request = Mock()
        response = self.view.get(mock_request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.status_code, 200)

    def test_get_returns_correct_data_structure(self):
        """Test that get method returns correct JSON structure."""
        mock_request = Mock()
        response = self.view.get(mock_request)

        self.assertIsInstance(response.data, dict)
        self.assertIn("status", response.data)

    def test_get_returns_status_ok(self):
        """Test that get method returns status 'ok' in response data."""
        mock_request = Mock()
        response = self.view.get(mock_request)

        self.assertEqual(response.data["status"], "ok")

    def test_get_returns_only_status_field(self):
        """Test that response contains only the status field."""
        mock_request = Mock()
        response = self.view.get(mock_request)

        self.assertEqual(len(response.data), 1)
        self.assertEqual(list(response.data.keys()), ["status"])

    def test_get_is_idempotent(self):
        """Test that multiple calls to get return the same result."""
        mock_request = Mock()

        response1 = self.view.get(mock_request)
        response2 = self.view.get(mock_request)

        self.assertEqual(response1.status_code, response2.status_code)
        self.assertEqual(response1.data, response2.data)

    def test_get_does_not_use_request_object(self):
        """Test that get method does not access request object."""
        # This tests the fact that request is unused (prefixed with _)
        mock_request = MagicMock()

        self.view.get(mock_request)

        # The request should not have any methods called on it
        # since the parameter is named _request (unused)
        self.assertEqual(mock_request.method_calls, [])

    def test_get_accepts_any_request_including_none(self):
        """Test that get method works even with None request."""
        # Since request is unused, None should work fine
        response = self.view.get(None)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")

    def test_view_class_has_docstring(self):
        """Test that HealthCheckView has a docstring."""
        self.assertIsNotNone(HealthCheckView.__doc__)
        self.assertIn("health check", HealthCheckView.__doc__.lower())

    def test_get_method_has_docstring(self):
        """Test that get method has a docstring."""
        self.assertIsNotNone(self.view.get.__doc__)
        self.assertIn("GET", self.view.get.__doc__)


class TestHealthCheckViewResponseContent(unittest.TestCase):
    """Tests focusing on response content validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.view = HealthCheckView()
        self.mock_request = Mock()

    def test_response_data_is_serializable(self):
        """Test that response data can be serialized to JSON."""
        response = self.view.get(self.mock_request)

        # Response data should be JSON-serializable
        try:
            json.dumps(response.data)
        except (TypeError, ValueError):
            self.fail("Response data is not JSON serializable")

    def test_status_value_is_string(self):
        """Test that status value is a string."""
        response = self.view.get(self.mock_request)

        self.assertIsInstance(response.data["status"], str)

    def test_status_value_is_lowercase(self):
        """Test that status value is lowercase."""
        response = self.view.get(self.mock_request)

        self.assertEqual(response.data["status"], response.data["status"].lower())

    def test_response_data_is_dict_not_list(self):
        """Test that response data is a dictionary, not a list."""
        response = self.view.get(self.mock_request)

        self.assertIsInstance(response.data, dict)
        self.assertNotIsInstance(response.data, list)


if __name__ == "__main__":
    unittest.main()
