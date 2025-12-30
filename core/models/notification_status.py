"""NotificationStatus model for per-channel delivery tracking.

This module defines the notification status model which tracks delivery
attempts per channel (EMAIL, IN_APP, PUSH, SMS) for each notification.
"""

from typing import ClassVar

from django.db import models
from django.utils import timezone


class NotificationStatus(models.Model):
    """Delivery status tracking per notification channel.

    This model tracks the delivery status for each channel a notification
    is sent through. A single Notification can have multiple NotificationStatus
    records (one per delivery channel).

    The database uses a composite primary key of (notification_id, notification_type).
    Django models this with unique_together and an implicit id field.

    Attributes:
        notification: Reference to the parent Notification.
        notification_type: Delivery channel (EMAIL, IN_APP, PUSH, SMS).
        status: Current delivery status (PENDING, QUEUED, SENT, FAILED, ABORTED).
        retry_count: Number of delivery attempts (NULL if no retries).
        error_message: Error details if delivery failed.
        recipient_email: Email address for EMAIL type delivery.
        created_at: When the status record was created.
        updated_at: When the status was last updated.
        queued_at: When queued for delivery.
        sent_at: When successfully sent.
        failed_at: When permanently failed.
    """

    notification = models.ForeignKey(
        "core.Notification",
        on_delete=models.CASCADE,
        related_name="statuses",
        db_column="notification_id",
        help_text="Parent notification",
    )
    notification_type = models.CharField(
        max_length=20,
        help_text="Delivery channel type (EMAIL, IN_APP, PUSH, SMS)",
    )
    status = models.CharField(
        max_length=20,
        default="PENDING",
        help_text="Delivery status (PENDING, QUEUED, SENT, FAILED, ABORTED)",
    )
    retry_count = models.IntegerField(
        null=True,
        blank=True,
        help_text="Number of delivery attempts (NULL if no retries)",
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error details if delivery failed",
    )
    recipient_email = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Email address for EMAIL type delivery",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the status record was created",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the status was last updated",
    )
    queued_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When queued for delivery",
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When successfully sent",
    )
    failed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When permanently failed",
    )

    class Meta:
        """Django model metadata."""

        db_table = "notification_statuses"
        managed = False
        ordering: ClassVar[list[str]] = ["-created_at"]
        unique_together: ClassVar[list[list[str]]] = [
            ["notification", "notification_type"]
        ]
        indexes: ClassVar[list] = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["notification", "notification_type"]),
        ]

    def __str__(self) -> str:
        """Return string representation of notification status."""
        return f"{self.notification_type} - {self.status}"

    def __repr__(self) -> str:
        """Return detailed representation of notification status."""
        return (
            f"<NotificationStatus(notification={self.notification_id}, "
            f"type={self.notification_type}, "
            f"status={self.status})>"
        )

    def mark_queued(self) -> None:
        """Mark status as queued for processing."""
        self.status = "QUEUED"
        self.queued_at = timezone.now()
        self.save(update_fields=["status", "queued_at", "updated_at"])

    def mark_sent(self) -> None:
        """Mark status as successfully sent."""
        self.status = "SENT"
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at", "updated_at"])

    def mark_failed(self, error_msg: str) -> None:
        """Mark status as failed with error message.

        Args:
            error_msg: Description of the failure.
        """
        self.status = "FAILED"
        self.failed_at = timezone.now()
        self.error_message = error_msg
        self.save(update_fields=["status", "failed_at", "error_message", "updated_at"])

    def increment_retry(self) -> None:
        """Increment retry count."""
        if self.retry_count is None:
            self.retry_count = 1
        else:
            self.retry_count += 1
        self.save(update_fields=["retry_count", "updated_at"])

    def can_retry(self, max_retries: int = 3) -> bool:
        """Check if status can be retried.

        Args:
            max_retries: Maximum number of retry attempts allowed.

        Returns:
            True if retry is possible, False otherwise.
        """
        current_retries = self.retry_count or 0
        return current_retries < max_retries and self.status != "SENT"
