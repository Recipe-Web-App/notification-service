"""Tests for UserClient."""

from uuid import uuid4

import pytest
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


class TestUserClient:
    """Test suite for UserClient."""

    @pytest.fixture
    def user_client(self):
        """Create UserClient instance."""
        return UserClient()

    @pytest.fixture
    def sample_user_data(self):
        """Sample user response data from user-management service."""
        return {
            "userId": str(uuid4()),
            "username": "johndoe",
            "fullName": "John Doe",
            "isActive": True,
            "createdAt": "2025-10-01T10:00:00Z",
            "updatedAt": "2025-10-28T12:00:00Z",
        }

    @responses.activate
    def test_get_user_success(self, user_client, sample_user_data):
        """Test successful user fetch."""
        user_id = sample_user_data["userId"]
        url = f"{user_client.base_url}/user-management/users/{user_id}"

        # Mock the HTTP response
        responses.add(
            responses.GET,
            url,
            json=sample_user_data,
            status=200,
        )

        # Fetch user
        user = user_client.get_user(user_id)

        # Assertions
        assert isinstance(user, UserSearchResult)
        assert str(user.user_id) == user_id
        assert user.username == "johndoe"
        assert user.full_name == "John Doe"
        assert user.is_active is True

        # Verify request had no authorization header (public endpoint)
        assert len(responses.calls) == 1
        assert "Authorization" not in responses.calls[0].request.headers

    @responses.activate
    def test_get_user_not_found(self, user_client):
        """Test user not found (404) raises UserNotFoundError."""
        user_id = str(uuid4())
        url = f"{user_client.base_url}/user-management/users/{user_id}"

        # Mock 404 response
        responses.add(
            responses.GET,
            url,
            json={"detail": "User not found"},
            status=404,
        )

        # Should raise UserNotFoundError
        with pytest.raises(UserNotFoundError) as exc_info:
            user_client.get_user(user_id)

        assert exc_info.value.user_id == user_id
        assert exc_info.value.status_code == 404
        assert user_id in str(exc_info.value)

    @responses.activate
    def test_get_user_server_error(self, user_client):
        """Test server error (500) raises DownstreamServiceUnavailableError."""
        user_id = str(uuid4())
        url = f"{user_client.base_url}/user-management/users/{user_id}"

        # Mock 500 response
        responses.add(
            responses.GET,
            url,
            json={"error": "Internal server error"},
            status=500,
        )

        # Should raise DownstreamServiceUnavailableError
        with pytest.raises(DownstreamServiceUnavailableError) as exc_info:
            user_client.get_user(user_id)

        assert exc_info.value.status_code == 500
        assert exc_info.value.service_name == "user-management"

    @responses.activate
    def test_get_user_service_unavailable(self, user_client):
        """Test service unavailable (503) raises DownstreamServiceUnavailableError."""
        user_id = str(uuid4())
        url = f"{user_client.base_url}/user-management/users/{user_id}"

        # Mock 503 response
        responses.add(
            responses.GET,
            url,
            json={"error": "Service temporarily unavailable"},
            status=503,
        )

        # Should raise DownstreamServiceUnavailableError
        with pytest.raises(DownstreamServiceUnavailableError) as exc_info:
            user_client.get_user(user_id)

        assert exc_info.value.status_code == 503

    @responses.activate
    def test_get_user_validation_error(self, user_client):
        """Test validation error (422) raises DownstreamServiceError."""
        user_id = "invalid-uuid"
        url = f"{user_client.base_url}/user-management/users/{user_id}"

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
        with pytest.raises(DownstreamServiceError) as exc_info:
            user_client.get_user(user_id)

        assert exc_info.value.status_code == 422

    @responses.activate
    def test_get_user_timeout(self, user_client):
        """Test request timeout raises requests.Timeout."""
        user_id = str(uuid4())
        url = f"{user_client.base_url}/user-management/users/{user_id}"

        # Mock timeout
        responses.add(
            responses.GET,
            url,
            body=requests.Timeout("Connection timeout"),
        )

        # Should raise requests.Timeout
        with pytest.raises(requests.Timeout):
            user_client.get_user(user_id)

    @responses.activate
    def test_get_user_connection_error(self, user_client):
        """Test connection error raises requests.ConnectionError."""
        user_id = str(uuid4())
        url = f"{user_client.base_url}/user-management/users/{user_id}"

        # Mock connection error
        responses.add(
            responses.GET,
            url,
            body=requests.ConnectionError("Connection refused"),
        )

        # Should raise requests.ConnectionError
        with pytest.raises(requests.ConnectionError):
            user_client.get_user(user_id)

    @responses.activate
    def test_get_user_invalid_response_data(self, user_client):
        """Test invalid response data raises ValidationError."""
        user_id = str(uuid4())
        url = f"{user_client.base_url}/user-management/users/{user_id}"

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
        with pytest.raises(ValidationError):
            user_client.get_user(user_id)

    @responses.activate
    def test_get_user_without_full_name(self, user_client):
        """Test user response without optional fullName field."""
        user_id = str(uuid4())
        url = f"{user_client.base_url}/user-management/users/{user_id}"

        # Mock response without fullName (optional field)
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
        user = user_client.get_user(user_id)

        # Assertions
        assert user.username == "johndoe"
        assert user.full_name is None  # Optional field should be None
        assert user.is_active is True

    @responses.activate
    def test_get_user_inactive(self, user_client):
        """Test fetching inactive user."""
        user_id = str(uuid4())
        url = f"{user_client.base_url}/user-management/users/{user_id}"

        # Mock response for inactive user
        user_data = {
            "userId": user_id,
            "username": "inactiveuser",
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
        user = user_client.get_user(user_id)

        # Assertions
        assert user.is_active is False
        assert user.username == "inactiveuser"

    def test_user_client_no_auth_required(self, user_client):
        """Test that UserClient is configured to not require authentication."""
        # Verify requires_auth is False
        assert user_client.requires_auth is False

    @responses.activate
    def test_get_user_headers_no_authorization(self, user_client):
        """Test that requests do not include Authorization header."""
        user_id = str(uuid4())
        url = f"{user_client.base_url}/user-management/users/{user_id}"

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
        user_client.get_user(user_id)

        # Verify no Authorization header
        request_headers = responses.calls[0].request.headers
        assert "Authorization" not in request_headers
        assert "Content-Type" in request_headers
        assert request_headers["Content-Type"] == "application/json"
