"""Notification-related enumerations.

This module contains enums for notification types, delivery statuses,
and notification categories used throughout the notification service.
"""

from enum import Enum


class NotificationType(str, Enum):
    """Notification delivery channel types.

    Defines the channels through which notifications can be delivered.
    Each notification can be sent via multiple channels simultaneously.
    """

    EMAIL = "EMAIL"
    IN_APP = "IN_APP"
    PUSH = "PUSH"
    SMS = "SMS"


class NotificationStatusEnum(str, Enum):
    """Notification delivery status values.

    Tracks the lifecycle of a notification delivery attempt.
    Named with 'Enum' suffix to avoid clash with NotificationStatus model.
    """

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class NotificationCategory(str, Enum):
    """Notification categories for template identification.

    Each category maps to a specific notification template and determines
    the expected structure of notification_data and how title/message
    are rendered.
    """

    # Recipe events
    RECIPE_PUBLISHED = "RECIPE_PUBLISHED"
    RECIPE_LIKED = "RECIPE_LIKED"
    RECIPE_COMMENTED = "RECIPE_COMMENTED"
    RECIPE_SHARED = "RECIPE_SHARED"
    RECIPE_COLLECTED = "RECIPE_COLLECTED"
    RECIPE_RATED = "RECIPE_RATED"
    RECIPE_FEATURED = "RECIPE_FEATURED"
    RECIPE_TRENDING = "RECIPE_TRENDING"

    # Social events
    NEW_FOLLOWER = "NEW_FOLLOWER"
    MENTION = "MENTION"
    COLLECTION_INVITE = "COLLECTION_INVITE"

    # System events
    WELCOME = "WELCOME"
    PASSWORD_RESET = "PASSWORD_RESET"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    EMAIL_CHANGED = "EMAIL_CHANGED"
    MAINTENANCE = "MAINTENANCE"
    SYSTEM_ALERT = "SYSTEM_ALERT"
