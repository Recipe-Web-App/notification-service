"""Tests for RecipeManagementServiceClient."""

from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
import requests
import responses
from pydantic import ValidationError

from core.exceptions import (
    DownstreamServiceError,
    DownstreamServiceUnavailableError,
    RecipeNotFoundError,
)
from core.schemas.recipe import RecipeDto
from core.services.downstream import RecipeManagementServiceClient


class TestRecipeManagementServiceClient:
    """Test suite for RecipeManagementServiceClient."""

    @pytest.fixture
    def recipe_client(self):
        """Create RecipeManagementServiceClient instance."""
        return RecipeManagementServiceClient()

    @pytest.fixture
    def sample_recipe_data(self):
        """Sample recipe response data from recipe-management service."""
        return {
            "recipeId": 123,
            "userId": str(uuid4()),
            "title": "Chocolate Chip Cookies",
            "servings": "24",
            "createdAt": "2025-10-28T12:00:00Z",
            "description": "Delicious homemade cookies",
            "preparationTime": 15,
            "cookingTime": 12,
            "difficulty": "EASY",
            "originUrl": "https://example.com/recipe",
            "updatedAt": "2025-10-28T13:00:00Z",
        }

    @pytest.fixture
    def mock_oauth_token(self):
        """Mock OAuth2 token retrieval."""
        with patch(
            "core.services.downstream.base_downstream_client.oauth2_client_service.get_access_token"
        ) as mock:
            mock.return_value = "test-access-token"
            yield mock

    @responses.activate
    def test_get_recipe_success(
        self, recipe_client, sample_recipe_data, mock_oauth_token
    ):
        """Test successful recipe fetch."""
        recipe_id = 123
        url = f"{recipe_client.base_url}/recipes/{recipe_id}"

        # Mock the HTTP response
        responses.add(
            responses.GET,
            url,
            json=sample_recipe_data,
            status=200,
        )

        # Fetch recipe
        recipe = recipe_client.get_recipe(recipe_id)

        # Assertions
        assert isinstance(recipe, RecipeDto)
        assert recipe.recipe_id == 123
        assert recipe.title == "Chocolate Chip Cookies"
        assert recipe.servings == Decimal("24")
        assert recipe.difficulty == "EASY"
        assert recipe.preparation_time == 15
        assert recipe.cooking_time == 12

        # Verify OAuth token was requested
        mock_oauth_token.assert_called_once()

        # Verify request had authorization header
        assert len(responses.calls) == 1
        assert (
            responses.calls[0].request.headers["Authorization"]
            == "Bearer test-access-token"
        )

    @responses.activate
    def test_get_recipe_not_found(self, recipe_client, mock_oauth_token):
        """Test recipe not found (404) raises RecipeNotFoundError."""
        recipe_id = 999
        url = f"{recipe_client.base_url}/recipes/{recipe_id}"

        # Mock 404 response
        responses.add(
            responses.GET,
            url,
            json={"detail": "Recipe not found"},
            status=404,
        )

        # Should raise RecipeNotFoundError
        with pytest.raises(RecipeNotFoundError) as exc_info:
            recipe_client.get_recipe(recipe_id)

        assert exc_info.value.recipe_id == recipe_id
        assert exc_info.value.status_code == 404
        assert "999" in str(exc_info.value)

    @responses.activate
    def test_get_recipe_server_error(self, recipe_client, mock_oauth_token):
        """Test server error (500) raises DownstreamServiceUnavailableError."""
        recipe_id = 123
        url = f"{recipe_client.base_url}/recipes/{recipe_id}"

        # Mock 500 response
        responses.add(
            responses.GET,
            url,
            json={"error": "Internal server error"},
            status=500,
        )

        # Should raise DownstreamServiceUnavailableError
        with pytest.raises(DownstreamServiceUnavailableError) as exc_info:
            recipe_client.get_recipe(recipe_id)

        assert exc_info.value.status_code == 500
        assert exc_info.value.service_name == "recipe-management"

    @responses.activate
    def test_get_recipe_service_unavailable(self, recipe_client, mock_oauth_token):
        """Test service unavailable (503) raises DownstreamServiceUnavailableError."""
        recipe_id = 123
        url = f"{recipe_client.base_url}/recipes/{recipe_id}"

        # Mock 503 response
        responses.add(
            responses.GET,
            url,
            json={"error": "Service temporarily unavailable"},
            status=503,
        )

        # Should raise DownstreamServiceUnavailableError
        with pytest.raises(DownstreamServiceUnavailableError) as exc_info:
            recipe_client.get_recipe(recipe_id)

        assert exc_info.value.status_code == 503

    @responses.activate
    def test_get_recipe_unauthorized(self, recipe_client, mock_oauth_token):
        """Test unauthorized (401) raises DownstreamServiceError."""
        recipe_id = 123
        url = f"{recipe_client.base_url}/recipes/{recipe_id}"

        # Mock 401 response
        responses.add(
            responses.GET,
            url,
            json={"error": "Unauthorized"},
            status=401,
        )

        # Should raise DownstreamServiceError
        with pytest.raises(DownstreamServiceError) as exc_info:
            recipe_client.get_recipe(recipe_id)

        assert exc_info.value.status_code == 401

    @responses.activate
    def test_get_recipe_timeout(self, recipe_client, mock_oauth_token):
        """Test request timeout raises requests.Timeout."""
        recipe_id = 123
        url = f"{recipe_client.base_url}/recipes/{recipe_id}"

        # Mock timeout
        responses.add(
            responses.GET,
            url,
            body=requests.Timeout("Connection timeout"),
        )

        # Should raise requests.Timeout
        with pytest.raises(requests.Timeout):
            recipe_client.get_recipe(recipe_id)

    @responses.activate
    def test_get_recipe_connection_error(self, recipe_client, mock_oauth_token):
        """Test connection error raises requests.ConnectionError."""
        recipe_id = 123
        url = f"{recipe_client.base_url}/recipes/{recipe_id}"

        # Mock connection error
        responses.add(
            responses.GET,
            url,
            body=requests.ConnectionError("Connection refused"),
        )

        # Should raise requests.ConnectionError
        with pytest.raises(requests.ConnectionError):
            recipe_client.get_recipe(recipe_id)

    @responses.activate
    def test_get_recipe_invalid_response_data(self, recipe_client, mock_oauth_token):
        """Test invalid response data raises ValidationError."""
        recipe_id = 123
        url = f"{recipe_client.base_url}/recipes/{recipe_id}"

        # Mock response with invalid data (missing required fields)
        responses.add(
            responses.GET,
            url,
            json={
                "recipeId": 123,
                # Missing required fields: userId, title, servings, createdAt
            },
            status=200,
        )

        # Should raise ValidationError (from Pydantic)
        with pytest.raises(ValidationError):
            recipe_client.get_recipe(recipe_id)

    def test_get_recipe_oauth_failure(self, recipe_client):
        """Test OAuth token fetch failure raises DownstreamServiceError."""
        recipe_id = 123

        # Mock OAuth failure
        with patch(
            "core.services.downstream.base_downstream_client.oauth2_client_service.get_access_token"
        ) as mock_oauth:
            mock_oauth.side_effect = Exception("OAuth token fetch failed")

            # Should raise DownstreamServiceError
            with pytest.raises(DownstreamServiceError) as exc_info:
                recipe_client.get_recipe(recipe_id)

            assert "Failed to authenticate" in str(exc_info.value)

    @responses.activate
    def test_get_recipe_minimal_response(self, recipe_client, mock_oauth_token):
        """Test recipe with only required fields."""
        recipe_id = 456
        url = f"{recipe_client.base_url}/recipes/{recipe_id}"

        # Mock response with only required fields
        minimal_data = {
            "recipeId": 456,
            "userId": str(uuid4()),
            "title": "Simple Recipe",
            "servings": "4",
            "createdAt": "2025-10-28T12:00:00Z",
        }

        responses.add(
            responses.GET,
            url,
            json=minimal_data,
            status=200,
        )

        # Fetch recipe
        recipe = recipe_client.get_recipe(recipe_id)

        # Assertions
        assert recipe.recipe_id == 456
        assert recipe.title == "Simple Recipe"
        assert recipe.description is None
        assert recipe.preparation_time is None
        assert recipe.cooking_time is None
        assert recipe.difficulty is None
