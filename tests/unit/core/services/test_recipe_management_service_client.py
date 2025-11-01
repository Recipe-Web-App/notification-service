"""Tests for RecipeManagementServiceClient."""

from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase

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


class TestRecipeManagementServiceClient(TestCase):
    """Test suite for RecipeManagementServiceClient."""

    def setUp(self):
        """Set up test fixtures."""
        self.recipe_client = RecipeManagementServiceClient()

        self.sample_recipe_data = {
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

    @responses.activate
    @patch(
        "core.services.downstream.base_downstream_client.oauth2_client_service.get_access_token"
    )
    def test_get_recipe_success(self, mock_oauth_token):
        """Test successful recipe fetch."""
        mock_oauth_token.return_value = "test-access-token"

        recipe_id = 123
        url = f"{self.recipe_client.base_url}/recipes/{recipe_id}"

        # Mock the HTTP response
        responses.add(
            responses.GET,
            url,
            json=self.sample_recipe_data,
            status=200,
        )

        # Fetch recipe
        recipe = self.recipe_client.get_recipe(recipe_id)

        # Assertions
        self.assertIsInstance(recipe, RecipeDto)
        self.assertEqual(recipe.recipe_id, 123)
        self.assertEqual(recipe.title, "Chocolate Chip Cookies")
        self.assertEqual(recipe.servings, Decimal("24"))
        self.assertEqual(recipe.difficulty, "EASY")
        self.assertEqual(recipe.preparation_time, 15)
        self.assertEqual(recipe.cooking_time, 12)

        # Verify OAuth token was requested
        mock_oauth_token.assert_called_once()

        # Verify request had authorization header
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(
            responses.calls[0].request.headers["Authorization"],
            "Bearer test-access-token",
        )

    @responses.activate
    @patch(
        "core.services.downstream.base_downstream_client.oauth2_client_service.get_access_token"
    )
    def test_get_recipe_not_found(self, mock_oauth_token):
        """Test recipe not found (404) raises RecipeNotFoundError."""
        mock_oauth_token.return_value = "test-access-token"

        recipe_id = 999
        url = f"{self.recipe_client.base_url}/recipes/{recipe_id}"

        # Mock 404 response
        responses.add(
            responses.GET,
            url,
            json={"detail": "Recipe not found"},
            status=404,
        )

        # Should raise RecipeNotFoundError
        with self.assertRaises(RecipeNotFoundError) as exc_info:
            self.recipe_client.get_recipe(recipe_id)

        self.assertEqual(exc_info.exception.recipe_id, recipe_id)
        self.assertEqual(exc_info.exception.status_code, 404)
        self.assertIn("999", str(exc_info.exception))

    @responses.activate
    @patch(
        "core.services.downstream.base_downstream_client.oauth2_client_service.get_access_token"
    )
    def test_get_recipe_server_error(self, mock_oauth_token):
        """Test server error (500) raises DownstreamServiceUnavailableError."""
        mock_oauth_token.return_value = "test-access-token"

        recipe_id = 123
        url = f"{self.recipe_client.base_url}/recipes/{recipe_id}"

        # Mock 500 response
        responses.add(
            responses.GET,
            url,
            json={"error": "Internal server error"},
            status=500,
        )

        # Should raise DownstreamServiceUnavailableError
        with self.assertRaises(DownstreamServiceUnavailableError) as exc_info:
            self.recipe_client.get_recipe(recipe_id)

        self.assertEqual(exc_info.exception.status_code, 500)
        self.assertEqual(exc_info.exception.service_name, "recipe-management")

    @responses.activate
    @patch(
        "core.services.downstream.base_downstream_client.oauth2_client_service.get_access_token"
    )
    def test_get_recipe_service_unavailable(self, mock_oauth_token):
        """Test service unavailable (503) raises DownstreamServiceUnavailableError."""
        mock_oauth_token.return_value = "test-access-token"

        recipe_id = 123
        url = f"{self.recipe_client.base_url}/recipes/{recipe_id}"

        # Mock 503 response
        responses.add(
            responses.GET,
            url,
            json={"error": "Service temporarily unavailable"},
            status=503,
        )

        # Should raise DownstreamServiceUnavailableError
        with self.assertRaises(DownstreamServiceUnavailableError) as exc_info:
            self.recipe_client.get_recipe(recipe_id)

        self.assertEqual(exc_info.exception.status_code, 503)

    @responses.activate
    @patch(
        "core.services.downstream.base_downstream_client.oauth2_client_service.get_access_token"
    )
    def test_get_recipe_unauthorized(self, mock_oauth_token):
        """Test unauthorized (401) raises DownstreamServiceError."""
        mock_oauth_token.return_value = "test-access-token"

        recipe_id = 123
        url = f"{self.recipe_client.base_url}/recipes/{recipe_id}"

        # Mock 401 response
        responses.add(
            responses.GET,
            url,
            json={"error": "Unauthorized"},
            status=401,
        )

        # Should raise DownstreamServiceError
        with self.assertRaises(DownstreamServiceError) as exc_info:
            self.recipe_client.get_recipe(recipe_id)

        self.assertEqual(exc_info.exception.status_code, 401)

    @responses.activate
    @patch(
        "core.services.downstream.base_downstream_client.oauth2_client_service.get_access_token"
    )
    def test_get_recipe_timeout(self, mock_oauth_token):
        """Test request timeout raises requests.Timeout."""
        mock_oauth_token.return_value = "test-access-token"

        recipe_id = 123
        url = f"{self.recipe_client.base_url}/recipes/{recipe_id}"

        # Mock timeout
        responses.add(
            responses.GET,
            url,
            body=requests.Timeout("Connection timeout"),
        )

        # Should raise requests.Timeout
        with self.assertRaises(requests.Timeout):
            self.recipe_client.get_recipe(recipe_id)

    @responses.activate
    @patch(
        "core.services.downstream.base_downstream_client.oauth2_client_service.get_access_token"
    )
    def test_get_recipe_connection_error(self, mock_oauth_token):
        """Test connection error raises requests.ConnectionError."""
        mock_oauth_token.return_value = "test-access-token"

        recipe_id = 123
        url = f"{self.recipe_client.base_url}/recipes/{recipe_id}"

        # Mock connection error
        responses.add(
            responses.GET,
            url,
            body=requests.ConnectionError("Connection refused"),
        )

        # Should raise requests.ConnectionError
        with self.assertRaises(requests.ConnectionError):
            self.recipe_client.get_recipe(recipe_id)

    @responses.activate
    @patch(
        "core.services.downstream.base_downstream_client.oauth2_client_service.get_access_token"
    )
    def test_get_recipe_invalid_response_data(self, mock_oauth_token):
        """Test invalid response data raises ValidationError."""
        mock_oauth_token.return_value = "test-access-token"

        recipe_id = 123
        url = f"{self.recipe_client.base_url}/recipes/{recipe_id}"

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
        with self.assertRaises(ValidationError):
            self.recipe_client.get_recipe(recipe_id)

    @patch(
        "core.services.downstream.base_downstream_client.oauth2_client_service.get_access_token"
    )
    def test_get_recipe_oauth_failure(self, mock_oauth):
        """Test OAuth token fetch failure raises DownstreamServiceError."""
        recipe_id = 123

        # Mock OAuth failure
        mock_oauth.side_effect = Exception("OAuth token fetch failed")

        # Should raise DownstreamServiceError
        with self.assertRaises(DownstreamServiceError) as exc_info:
            self.recipe_client.get_recipe(recipe_id)

        self.assertIn("Failed to authenticate", str(exc_info.exception))

    @responses.activate
    @patch(
        "core.services.downstream.base_downstream_client.oauth2_client_service.get_access_token"
    )
    def test_get_recipe_minimal_response(self, mock_oauth_token):
        """Test recipe with only required fields."""
        mock_oauth_token.return_value = "test-access-token"

        recipe_id = 456
        url = f"{self.recipe_client.base_url}/recipes/{recipe_id}"

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
        recipe = self.recipe_client.get_recipe(recipe_id)

        # Assertions
        self.assertEqual(recipe.recipe_id, 456)
        self.assertEqual(recipe.title, "Simple Recipe")
        self.assertIsNone(recipe.description)
        self.assertIsNone(recipe.preparation_time)
        self.assertIsNone(recipe.cooking_time)
        self.assertIsNone(recipe.difficulty)
