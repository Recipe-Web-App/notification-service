"""Downstream service clients package."""

from core.services.downstream.recipe_management_service_client import (
    RecipeManagementServiceClient,
    recipe_management_service_client,
)
from core.services.downstream.user_client import UserClient, user_client

__all__ = [
    "RecipeManagementServiceClient",
    "UserClient",
    "recipe_management_service_client",
    "user_client",
]
