"""Downstream service URL configuration.

This module contains base URLs for downstream services.
Future enhancement: Implement environment-based URL switching (prod vs non-prod).
"""

# Recipe Management Service
RECIPE_SERVICE_BASE_URL = "http://localhost:8080/api/v1/recipe-management"

# User Management Service
USER_SERVICE_BASE_URL = "http://localhost:8000/api/v1"
