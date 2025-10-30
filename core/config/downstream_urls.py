"""Downstream service URL configuration.

This module contains base URLs for downstream services and frontend.
Future enhancement: Implement environment-based URL switching (prod vs non-prod).
"""

import os

# Recipe Management Service
RECIPE_SERVICE_BASE_URL = "http://localhost:8080/api/v1/recipe-management"

# User Management Service
USER_SERVICE_BASE_URL = "http://localhost:8000/api/v1"

# Frontend Base URL - used to construct links in emails and notifications
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")
