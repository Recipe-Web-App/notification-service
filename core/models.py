"""Database models for core application."""

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


class UserFollow(models.Model):
    """User follow relationship model matching recipe_manager.user_follows table.

    This model tracks follower relationships between users.
    This model is unmanaged as the database schema is owned by another service.
    """

    follower = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="following",
        db_column="follower_id",
    )
    followee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="followers",
        db_column="followee_id",
    )
    followed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Django model metadata."""

        db_table = "user_follows"
        managed = False  # Schema is managed externally
        unique_together: ClassVar[list[list[str]]] = [["follower", "followee"]]
        ordering: ClassVar[list[str]] = ["-followed_at"]

    def __str__(self) -> str:
        """Return string representation of follow relationship."""
        return f"{self.follower.username} follows {self.followee.username}"

    def __repr__(self) -> str:
        """Return detailed representation of follow relationship."""
        return (
            f"<UserFollow(follower={self.follower.username}, "
            f"followee={self.followee.username})>"
        )
