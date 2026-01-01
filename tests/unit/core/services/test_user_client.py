"""Tests for UserClient."""

from unittest.mock import patch
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
from core.schemas.user import UserProfileResponse
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
            "bio": "A sample bio",
            "isActive": True,
            "createdAt": "2025-10-01T10:00:00Z",
            "updatedAt": "2025-10-28T12:00:00Z",
        }

    @responses.activate
    @patch("core.services.downstream.base_downstream_client.oauth2_client_service")
    def test_get_user_success(self, mock_oauth2):
        """Test successful user profile fetch."""
        mock_oauth2.get_access_token.return_value = "test-token"

        user_id = self.sample_user_data["userId"]
        url = f"{self.user_client.base_url}/user-management/users/{user_id}/profile"

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
        self.assertIsInstance(user, UserProfileResponse)
        self.assertEqual(str(user.user_id), user_id)
        self.assertEqual(user.username, "johndoe")
        self.assertEqual(user.full_name, "John Doe")
        self.assertEqual(user.bio, "A sample bio")
        self.assertIs(user.is_active, True)

        # Verify request had authorization header (service-to-service auth)
        self.assertEqual(len(responses.calls), 1)
        self.assertIn("Authorization", responses.calls[0].request.headers)
        self.assertEqual(
            responses.calls[0].request.headers["Authorization"], "Bearer test-token"
        )

    @responses.activate
    @patch("core.services.downstream.base_downstream_client.oauth2_client_service")
    def test_get_user_not_found(self, mock_oauth2):
        """Test user not found (404) raises UserNotFoundError."""
        mock_oauth2.get_access_token.return_value = "test-token"

        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}/profile"

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
    @patch("core.services.downstream.base_downstream_client.oauth2_client_service")
    def test_get_user_server_error(self, mock_oauth2):
        """Test server error (500) raises DownstreamServiceUnavailableError."""
        mock_oauth2.get_access_token.return_value = "test-token"

        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}/profile"

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
    @patch("core.services.downstream.base_downstream_client.oauth2_client_service")
    def test_get_user_service_unavailable(self, mock_oauth2):
        """Test service unavailable (503) raises DownstreamServiceUnavailableError."""
        mock_oauth2.get_access_token.return_value = "test-token"

        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}/profile"

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
    @patch("core.services.downstream.base_downstream_client.oauth2_client_service")
    def test_get_user_validation_error(self, mock_oauth2):
        """Test validation error (422) raises DownstreamServiceError."""
        mock_oauth2.get_access_token.return_value = "test-token"

        user_id = "invalid-uuid"
        url = f"{self.user_client.base_url}/user-management/users/{user_id}/profile"

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
    @patch("core.services.downstream.base_downstream_client.oauth2_client_service")
    def test_get_user_timeout(self, mock_oauth2):
        """Test request timeout raises requests.Timeout."""
        mock_oauth2.get_access_token.return_value = "test-token"

        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}/profile"

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
    @patch("core.services.downstream.base_downstream_client.oauth2_client_service")
    def test_get_user_connection_error(self, mock_oauth2):
        """Test connection error raises requests.ConnectionError."""
        mock_oauth2.get_access_token.return_value = "test-token"

        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}/profile"

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
    @patch("core.services.downstream.base_downstream_client.oauth2_client_service")
    def test_get_user_invalid_response_data(self, mock_oauth2):
        """Test invalid response data raises ValidationError."""
        mock_oauth2.get_access_token.return_value = "test-token"

        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}/profile"

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
    @patch("core.services.downstream.base_downstream_client.oauth2_client_service")
    def test_get_user_without_optional_fields(self, mock_oauth2):
        """Test user response without optional fields (fullName, email, bio)."""
        mock_oauth2.get_access_token.return_value = "test-token"

        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}/profile"

        # Mock response without optional fields
        user_data = {
            "userId": user_id,
            "username": "johndoe",
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

        # Assertions - optional fields should be None
        self.assertEqual(user.username, "johndoe")
        self.assertIsNone(user.full_name)
        self.assertIsNone(user.email)
        self.assertIsNone(user.bio)
        self.assertIs(user.is_active, True)

    @responses.activate
    @patch("core.services.downstream.base_downstream_client.oauth2_client_service")
    def test_get_user_inactive(self, mock_oauth2):
        """Test fetching inactive user."""
        mock_oauth2.get_access_token.return_value = "test-token"

        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}/profile"

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

    def test_user_client_requires_auth(self):
        """Test that UserClient is configured to require authentication."""
        # Verify requires_auth is True for service-to-service auth
        self.assertIs(self.user_client.requires_auth, True)

    @responses.activate
    @patch("core.services.downstream.base_downstream_client.oauth2_client_service")
    def test_get_user_headers_include_authorization(self, mock_oauth2):
        """Test that requests include Authorization header."""
        mock_oauth2.get_access_token.return_value = "service-token-123"

        user_id = str(uuid4())
        url = f"{self.user_client.base_url}/user-management/users/{user_id}/profile"

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

        # Verify Authorization header is present
        request_headers = responses.calls[0].request.headers
        self.assertIn("Authorization", request_headers)
        self.assertEqual(request_headers["Authorization"], "Bearer service-token-123")
        self.assertIn("Content-Type", request_headers)
        self.assertEqual(request_headers["Content-Type"], "application/json")


class TestUserClientFollowerRelationship(TestCase):
    """Test suite for UserClient follower relationship validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.user_client = UserClient()
        self.follower_id = str(uuid4())
        self.followee_id = str(uuid4())

    @responses.activate
    @patch("core.services.downstream.base_downstream_client.oauth2_client_service")
    def test_validate_follower_relationship_exists(self, mock_oauth2):
        """Test when follower relationship exists."""
        mock_oauth2.get_access_token.return_value = "test-token"

        url = (
            f"{self.user_client.base_url}/user-management/users/"
            f"{self.follower_id}/following/{self.followee_id}"
        )

        # Mock response indicating relationship exists
        responses.add(
            responses.GET,
            url,
            json={
                "isFollowing": True,
                "followedAt": "2025-10-01T10:00:00Z",
            },
            status=200,
        )

        result = self.user_client.validate_follower_relationship(
            self.follower_id, self.followee_id
        )

        self.assertIs(result, True)

    @responses.activate
    @patch("core.services.downstream.base_downstream_client.oauth2_client_service")
    def test_validate_follower_relationship_not_exists(self, mock_oauth2):
        """Test when follower relationship does not exist."""
        mock_oauth2.get_access_token.return_value = "test-token"

        url = (
            f"{self.user_client.base_url}/user-management/users/"
            f"{self.follower_id}/following/{self.followee_id}"
        )

        # Mock response indicating relationship does not exist
        responses.add(
            responses.GET,
            url,
            json={
                "isFollowing": False,
                "followedAt": None,
            },
            status=200,
        )

        result = self.user_client.validate_follower_relationship(
            self.follower_id, self.followee_id
        )

        self.assertIs(result, False)

    @responses.activate
    @patch("core.services.downstream.base_downstream_client.oauth2_client_service")
    def test_validate_follower_relationship_user_not_found(self, mock_oauth2):
        """Test when user is not found (404)."""
        mock_oauth2.get_access_token.return_value = "test-token"

        url = (
            f"{self.user_client.base_url}/user-management/users/"
            f"{self.follower_id}/following/{self.followee_id}"
        )

        # Mock 404 response
        responses.add(
            responses.GET,
            url,
            json={"detail": "User not found"},
            status=404,
        )

        result = self.user_client.validate_follower_relationship(
            self.follower_id, self.followee_id
        )

        # Should return False when user not found
        self.assertIs(result, False)

    @responses.activate
    @patch("core.services.downstream.base_downstream_client.oauth2_client_service")
    def test_validate_follower_relationship_server_error(self, mock_oauth2):
        """Test when server returns error - should fail closed."""
        mock_oauth2.get_access_token.return_value = "test-token"

        url = (
            f"{self.user_client.base_url}/user-management/users/"
            f"{self.follower_id}/following/{self.followee_id}"
        )

        # Mock 500 response
        responses.add(
            responses.GET,
            url,
            json={"error": "Internal server error"},
            status=500,
        )

        result = self.user_client.validate_follower_relationship(
            self.follower_id, self.followee_id
        )

        # Should return False (fail closed) on server error
        self.assertIs(result, False)

    @responses.activate
    @patch("core.services.downstream.base_downstream_client.oauth2_client_service")
    def test_validate_follower_relationship_connection_error(self, mock_oauth2):
        """Test when connection fails - should fail closed."""
        mock_oauth2.get_access_token.return_value = "test-token"

        url = (
            f"{self.user_client.base_url}/user-management/users/"
            f"{self.follower_id}/following/{self.followee_id}"
        )

        # Mock connection error
        responses.add(
            responses.GET,
            url,
            body=requests.ConnectionError("Connection refused"),
        )

        result = self.user_client.validate_follower_relationship(
            self.follower_id, self.followee_id
        )

        # Should return False (fail closed) on connection error
        self.assertIs(result, False)
