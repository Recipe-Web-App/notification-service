"""Tests for UserClient."""

from uuid import uuid4

from django.test import TestCase

import requests
import responses
from pydantic import ValidationError

from core.exceptions import (
    DownstreamServiceError,
    DownstreamServiceUnavailableError,
    UserNotFoundError,
)
from core.schemas.user import UserSearchResult
from core.services.downstream import UserClient


class TestUserClient(TestCase):
    """Test suite for UserClient."""

    def setUp(self):
        """Set up test fixtures."""
        self.user_client = UserClient()

        self.sample_user_data = {
            "userId": str(uuid4()),
            "username": "johndoe",
            "email": "johndoe@example.com",
            "fullName": "John Doe",
            "isActive": True,
            "createdAt": "2025-10-01T10:00:00Z",
            "updatedAt": "2025-10-28T12:00:00Z",
        }

    @responses.activate
    def test_get_user_success(self):
        """Test successful user fetch."""
        user_id = self.sample_user_data["userId"]
        url = f"{self.user_client.base_url}/user-management/users/{user_id}"

        # Mock the HTTP response
        responses.add(
            responses.GET,
            url,
            json=self.sample_user_data,
            status=200,
        )

        # Fetch user
        user = self.user_client.get_user(user_id)

        # Assertions
        self.assertIsInstance(user, UserSearchResult)
        self.assertEqual(str(user.user_id), user_id)
        self.assertEqual(user.username, "johndoe")
        self.assertEqual(user.full_name, "John Doe")
        self.assertIs(user.is_active, True)

        # Verify request had no authorization header (public endpoint)
        self.assertEqual(len(responses.calls), 1)
        self.assertNotIn("Authorization", responses.calls[0].request.headers)

    @responses.activate
    def test_get_user_not_found(self):
        """Test user not found (404) raises UserNotFoundError."""
        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}"

        # Mock 404 response
        responses.add(
            responses.GET,
            url,
            json={"detail": "User not found"},
            status=404,
        )

        # Should raise UserNotFoundError
        with self.assertRaises(UserNotFoundError) as exc_info:
            self.user_client.get_user(user_id)

        self.assertEqual(exc_info.exception.user_id, user_id)
        self.assertEqual(exc_info.exception.status_code, 404)
        self.assertIn(user_id, str(exc_info.exception))

    @responses.activate
    def test_get_user_server_error(self):
        """Test server error (500) raises DownstreamServiceUnavailableError."""
        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}"

        # Mock 500 response
        responses.add(
            responses.GET,
            url,
            json={"error": "Internal server error"},
            status=500,
        )

        # Should raise DownstreamServiceUnavailableError
        with self.assertRaises(DownstreamServiceUnavailableError) as exc_info:
            self.user_client.get_user(user_id)

        self.assertEqual(exc_info.exception.status_code, 500)
        self.assertEqual(exc_info.exception.service_name, "user-management")

    @responses.activate
    def test_get_user_service_unavailable(self):
        """Test service unavailable (503) raises DownstreamServiceUnavailableError."""
        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}"

        # Mock 503 response
        responses.add(
            responses.GET,
            url,
            json={"error": "Service temporarily unavailable"},
            status=503,
        )

        # Should raise DownstreamServiceUnavailableError
        with self.assertRaises(DownstreamServiceUnavailableError) as exc_info:
            self.user_client.get_user(user_id)

        self.assertEqual(exc_info.exception.status_code, 503)

    @responses.activate
    def test_get_user_validation_error(self):
        """Test validation error (422) raises DownstreamServiceError."""
        user_id = "invalid-uuid"
        url = f"{self.user_client.base_url}/user-management/users/{user_id}"

        # Mock 422 response
        responses.add(
            responses.GET,
            url,
            json={
                "detail": [
                    {
                        "type": "uuid_parsing",
                        "loc": ["path", "user_id"],
                        "msg": "Input should be a valid UUID",
                    }
                ]
            },
            status=422,
        )

        # Should raise DownstreamServiceError
        with self.assertRaises(DownstreamServiceError) as exc_info:
            self.user_client.get_user(user_id)

        self.assertEqual(exc_info.exception.status_code, 422)

    @responses.activate
    def test_get_user_timeout(self):
        """Test request timeout raises requests.Timeout."""
        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}"

        # Mock timeout
        responses.add(
            responses.GET,
            url,
            body=requests.Timeout("Connection timeout"),
        )

        # Should raise requests.Timeout
        with self.assertRaises(requests.Timeout):
            self.user_client.get_user(user_id)

    @responses.activate
    def test_get_user_connection_error(self):
        """Test connection error raises requests.ConnectionError."""
        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}"

        # Mock connection error
        responses.add(
            responses.GET,
            url,
            body=requests.ConnectionError("Connection refused"),
        )

        # Should raise requests.ConnectionError
        with self.assertRaises(requests.ConnectionError):
            self.user_client.get_user(user_id)

    @responses.activate
    def test_get_user_invalid_response_data(self):
        """Test invalid response data raises ValidationError."""
        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}"

        # Mock response with invalid data (missing required fields)
        responses.add(
            responses.GET,
            url,
            json={
                "userId": user_id,
                "username": "johndoe",
                # Missing required fields: isActive, createdAt, updatedAt
            },
            status=200,
        )

        # Should raise ValidationError (from Pydantic)
        with self.assertRaises(ValidationError):
            self.user_client.get_user(user_id)

    @responses.activate
    def test_get_user_without_full_name(self):
        """Test user response without optional fullName field."""
        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}"

        # Mock response without fullName (optional field)
        user_data = {
            "userId": user_id,
            "username": "johndoe",
            "email": "johndoe@example.com",
            "isActive": True,
            "createdAt": "2025-10-01T10:00:00Z",
            "updatedAt": "2025-10-28T12:00:00Z",
        }

        responses.add(
            responses.GET,
            url,
            json=user_data,
            status=200,
        )

        # Fetch user
        user = self.user_client.get_user(user_id)

        # Assertions
        self.assertEqual(user.username, "johndoe")
        self.assertIsNone(user.full_name)  # Optional field should be None
        self.assertIs(user.is_active, True)

    @responses.activate
    def test_get_user_inactive(self):
        """Test fetching inactive user."""
        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}"

        # Mock response for inactive user
        user_data = {
            "userId": user_id,
            "username": "inactiveuser",
            "email": "inactive@example.com",
            "fullName": "Inactive User",
            "isActive": False,
            "createdAt": "2025-10-01T10:00:00Z",
            "updatedAt": "2025-10-28T12:00:00Z",
        }

        responses.add(
            responses.GET,
            url,
            json=user_data,
            status=200,
        )

        # Fetch user
        user = self.user_client.get_user(user_id)

        # Assertions
        self.assertIs(user.is_active, False)
        self.assertEqual(user.username, "inactiveuser")

    def test_user_client_no_auth_required(self):
        """Test that UserClient is configured to not require authentication."""
        # Verify requires_auth is False
        self.assertIs(self.user_client.requires_auth, False)

    @responses.activate
    def test_get_user_headers_no_authorization(self):
        """Test that requests do not include Authorization header."""
        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}"

        user_data = {
            "userId": user_id,
            "username": "johndoe",
            "email": "johndoe@example.com",
            "isActive": True,
            "createdAt": "2025-10-01T10:00:00Z",
            "updatedAt": "2025-10-28T12:00:00Z",
        }

        responses.add(
            responses.GET,
            url,
            json=user_data,
            status=200,
        )

        # Fetch user
        self.user_client.get_user(user_id)

        # Verify no Authorization header
        request_headers = responses.calls[0].request.headers
        self.assertNotIn("Authorization", request_headers)
        self.assertIn("Content-Type", request_headers)
        self.assertEqual(request_headers["Content-Type"], "application/json")
