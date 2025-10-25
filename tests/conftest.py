"""Pytest configuration and shared fixtures."""

import os

import django
from django.test import Client

import pytest

# Configure Django settings for tests
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "notification_service.settings_test")
django.setup()


@pytest.fixture
def api_client():
    """Provide Django test client."""
    return Client()


@pytest.fixture
def authenticated_client():
    """Provide authenticated test client."""
    client = Client()
    # Add authentication logic here
    return client
