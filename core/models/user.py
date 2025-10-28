"""User model."""

import uuid
from typing import ClassVar

from django.db import models

from core.enums import UserRole


class User(models.Model):
    """User model matching the recipe_manager.users table.

    This model is unmanaged as the database schema is owned by another service.
    It provides read-only access to user data for notification purposes.
    """

    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(
        max_length=10,
        choices=[(role.value, role.value) for role in UserRole],
        default=UserRole.USER.value,
    )
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(max_length=255, unique=True)
    password_hash = models.CharField(max_length=255)
    full_name = models.CharField(max_length=255, default="", blank=True)
    bio = models.TextField(default="", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Django model metadata."""

        db_table = "users"
        managed = False  # Schema is managed externally
        ordering: ClassVar[list[str]] = ["-created_at"]

    def __str__(self) -> str:
        """Return string representation of user."""
        return f"{self.username} ({self.email})"

    def __repr__(self) -> str:
        """Return detailed representation of user."""
        return f"<User(user_id={self.user_id}, username='{self.username}')>"
