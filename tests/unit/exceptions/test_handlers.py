"""Unit tests for exception handlers."""

import unittest
from unittest.mock import Mock, patch

from django.core.exceptions import PermissionDenied
from django.http import Http404

from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.views import APIView

from core.exceptions.handlers import custom_exception_handler


class TestCustomExceptionHandler(unittest.TestCase):
    """Test cases for custom exception handler."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_request = Mock()
        self.mock_request.path = "/test/"
        self.mock_request.method = "GET"
        self.mock_request.META = {"REMOTE_ADDR": "127.0.0.1"}

        self.mock_view = Mock(spec=APIView)
        self.mock_view.request = self.mock_request

        self.context = {"view": self.mock_view, "request": self.mock_request}

    @patch("core.exceptions.handlers.get_request_id")
    def test_handles_drf_not_found_exception(self, mock_get_request_id):
        """Test that DRF NotFound exception is handled correctly."""
        mock_get_request_id.return_value = "test-request-id"
        exc = NotFound("Resource not found")

        response = custom_exception_handler(exc, self.context)

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response["X-Request-ID"], "test-request-id")

    @patch("core.exceptions.handlers.get_request_id")
    def test_handles_drf_validation_error(self, mock_get_request_id):
        """Test that DRF ValidationError is handled correctly."""
        mock_get_request_id.return_value = "test-request-id"
        exc = ValidationError("Invalid data")

        response = custom_exception_handler(exc, self.context)

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("core.exceptions.handlers.get_request_id")
    def test_handles_django_http404(self, mock_get_request_id):
        """Test that Django Http404 exception is handled correctly."""
        mock_get_request_id.return_value = "test-request-id"
        exc = Http404("Page not found")

        response = custom_exception_handler(exc, self.context)

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # Check the response is a Response object with proper data
        self.assertTrue(hasattr(response, "data"))
        # Response should have the standard fields we set
        self.assertIsInstance(response.data, dict)

    @patch("core.exceptions.handlers.get_request_id")
    def test_handles_django_permission_denied(self, mock_get_request_id):
        """Test that Django PermissionDenied exception is handled correctly."""
        mock_get_request_id.return_value = "test-request-id"
        exc = PermissionDenied("Access denied")

        response = custom_exception_handler(exc, self.context)

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # Check the response is a Response object with proper data
        self.assertTrue(hasattr(response, "data"))
        self.assertIsInstance(response.data, dict)

    @patch("core.exceptions.handlers.get_request_id")
    def test_handles_unexpected_exception(self, mock_get_request_id):
        """Test that unexpected exceptions return 500 error."""
        mock_get_request_id.return_value = "test-request-id"
        exc = RuntimeError("Unexpected error")

        response = custom_exception_handler(exc, self.context)

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(response.data["status"], 500)
        self.assertIn("internal server error", response.data["message"].lower())

    @patch("core.exceptions.handlers.get_request_id")
    def test_error_response_format(self, mock_get_request_id):
        """Test that error response has standard format for unhandled exceptions."""
        mock_get_request_id.return_value = "test-request-id"
        # Use an unhandled exception type to get our custom format
        exc = RuntimeError("Test error")

        response = custom_exception_handler(exc, self.context)

        # Check standard response format for 500 errors
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIsInstance(response.data, dict)

    @patch("core.exceptions.handlers.get_request_id")
    @patch("core.exceptions.handlers.logger")
    def test_logs_exception_details(self, mock_logger, mock_get_request_id):
        """Test that exception details are logged."""
        mock_get_request_id.return_value = "test-request-id"
        exc = RuntimeError("Test error")

        custom_exception_handler(exc, self.context)

        # Verify logging was called
        self.assertTrue(mock_logger.log.called)

    @patch("core.exceptions.handlers.get_request_id")
    def test_adds_request_id_to_response_header(self, mock_get_request_id):
        """Test that request ID is added to response headers."""
        request_id = "unique-request-id"
        mock_get_request_id.return_value = request_id
        exc = Http404("Not found")

        response = custom_exception_handler(exc, self.context)

        self.assertEqual(response["X-Request-ID"], request_id)


if __name__ == "__main__":
    unittest.main()
