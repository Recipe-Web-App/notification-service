"""Downstream service clients package."""

from core.services.downstream.recipe_client import RecipeClient, recipe_client
from core.services.downstream.user_client import UserClient, user_client

__all__ = [
    "RecipeClient",
    "UserClient",
    "recipe_client",
    "user_client",
]
