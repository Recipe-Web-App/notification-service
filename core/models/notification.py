"""Notification model."""

import uuid
from typing import ClassVar

from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """Notification model for tracking email and other notifications.

    This model stores notification history with full audit trail.
    Notifications are queued via Django-RQ for reliable async delivery.
    """

    # Status choices
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"

    STATUS_CHOICES: ClassVar[list[tuple[str, str]]] = [
        (PENDING, "Pending"),
        (QUEUED, "Queued"),
        (SENT, "Sent"),
        (FAILED, "Failed"),
    ]

    # Notification type choices (extensible for future)
    EMAIL = "email"
    IN_APP = "in_app"
    PUSH = "push"
    SMS = "sms"

    TYPE_CHOICES: ClassVar[list[tuple[str, str]]] = [
        (EMAIL, "Email"),
        (IN_APP, "In-App"),
        (PUSH, "Push Notification"),
        (SMS, "SMS"),
    ]

    notification_id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    recipient = models.ForeignKey(
        "core.User",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
        db_column="recipient_id",
        help_text="User receiving the notification",
    )
    recipient_email = models.EmailField(
        max_length=255, help_text="Email address for delivery (may differ from user)"
    )
    subject = models.CharField(max_length=255, help_text="Email subject line")
    message = models.TextField(help_text="HTML or plain text message content")
    notification_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=EMAIL,
        help_text="Type of notification",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING,
        help_text="Current delivery status",
    )
    error_message = models.TextField(
        default="", blank=True, help_text="Error details if delivery failed"
    )
    retry_count = models.IntegerField(
        default=0, help_text="Number of delivery attempts"
    )
    max_retries = models.IntegerField(default=3, help_text="Maximum retry attempts")

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When notification was created"
    )
    queued_at = models.DateTimeField(
        null=True, blank=True, help_text="When notification was queued"
    )
    sent_at = models.DateTimeField(
        null=True, blank=True, help_text="When notification was successfully sent"
    )
    failed_at = models.DateTimeField(
        null=True, blank=True, help_text="When notification failed permanently"
    )

    # Metadata
    metadata = models.JSONField(
        null=True,
        blank=True,
        help_text="Additional metadata (template vars, tracking info, etc.)",
    )

    class Meta:
        """Django model metadata."""

        db_table = "notifications"
        managed = False  # Schema is managed externally
        ordering: ClassVar[list[str]] = ["-created_at"]
        indexes: ClassVar[list] = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["recipient", "-created_at"]),
            models.Index(fields=["recipient_email", "-created_at"]),
        ]

    def __str__(self) -> str:
        """Return string representation of notification."""
        return f"{self.notification_type} to {self.recipient_email} ({self.status})"

    def __repr__(self) -> str:
        """Return detailed representation of notification."""
        return (
            f"<Notification(id={self.notification_id}, "
            f"type={self.notification_type}, "
            f"status={self.status}, "
            f"recipient={self.recipient_email})>"
        )

    def mark_queued(self) -> None:
        """Mark notification as queued for processing."""
        self.status = self.QUEUED
        self.queued_at = timezone.now()
        self.save(update_fields=["status", "queued_at"])

    def mark_sent(self) -> None:
        """Mark notification as successfully sent."""
        self.status = self.SENT
        self.sent_at = timezone.now()
        self.save(update_fields=["status", "sent_at"])

    def mark_failed(self, error_msg: str) -> None:
        """Mark notification as failed with error message."""
        self.status = self.FAILED
        self.failed_at = timezone.now()
        self.error_message = error_msg
        self.save(update_fields=["status", "failed_at", "error_message"])

    def increment_retry(self) -> None:
        """Increment retry count."""
        self.retry_count += 1
        self.save(update_fields=["retry_count"])

    def can_retry(self) -> bool:
        """Check if notification can be retried."""
        return self.retry_count < self.max_retries and self.status != self.SENT
