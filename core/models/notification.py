"""Notification model for user-facing notification data.

This module defines the core notification model which stores user-facing
notification data. Delivery tracking is handled separately in the
NotificationStatus model.
"""

import uuid
from typing import ClassVar

from django.db import models


class Notification(models.Model):
    """Core notification model storing user-facing notification data.

    This model represents a single notification for a user. The title and
    message are computed on-the-fly from notification_category and
    notification_data - they are NOT stored in the database.

    Delivery tracking (status, retries, timestamps) is handled separately
    in the NotificationStatus model, which tracks delivery per channel
    (EMAIL, IN_APP, PUSH, SMS).

    Attributes:
        notification_id: Unique identifier for the notification.
        user: The user receiving this notification.
        notification_category: Category determining template and rendering.
        is_read: Whether the user has read this notification.
        is_deleted: Soft delete flag for user-initiated deletion.
        notification_data: JSONB containing template params and templateVersion.
        created_at: When the notification was created.
        updated_at: When the notification was last updated.
    """

    notification_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the notification",
    )
    user = models.ForeignKey(
        "core.User",
        on_delete=models.CASCADE,
        related_name="notifications",
        db_column="user_id",
        help_text="User receiving the notification",
    )
    notification_category = models.CharField(
        max_length=50,
        help_text="Category determining template and notification_data structure",
    )
    is_read = models.BooleanField(
        default=False,
        help_text="Whether the notification has been read by the user",
    )
    is_deleted = models.BooleanField(
        default=False,
        help_text="Soft delete flag for user-initiated deletion",
    )
    notification_data = models.JSONField(
        help_text="Template parameters including templateVersion for rendering",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the notification was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the notification was last updated",
    )

    class Meta:
        """Django model metadata."""

        db_table = "notifications"
        managed = False
        ordering: ClassVar[list[str]] = ["-created_at"]
        indexes: ClassVar[list] = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "is_read", "-created_at"]),
            models.Index(fields=["user", "is_deleted", "-created_at"]),
        ]

    def __str__(self) -> str:
        """Return string representation of notification."""
        return f"{self.notification_category} for user {self.user_id}"

    def __repr__(self) -> str:
        """Return detailed representation of notification."""
        return (
            f"<Notification(id={self.notification_id}, "
            f"category={self.notification_category}, "
            f"user={self.user_id}, "
            f"is_read={self.is_read})>"
        )
