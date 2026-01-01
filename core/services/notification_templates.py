"""Email template configuration for notification categories.

This module provides a centralized registry mapping notification categories
to their email subject templates and HTML template paths. Email rendering
is performed at send time by the email job.
"""

from typing import TypedDict


class EmailTemplateConfig(TypedDict):
    """Configuration for an email template."""

    subject: str
    template: str


EMAIL_TEMPLATES: dict[str, EmailTemplateConfig] = {
    # Recipe events
    "RECIPE_PUBLISHED": {
        "subject": "New Recipe: {recipe_title}",
        "template": "emails/recipe_published.html",
    },
    "RECIPE_LIKED": {
        "subject": "{actor_name} liked your recipe",
        "template": "emails/recipe_liked.html",
    },
    "RECIPE_COMMENTED": {
        "subject": "New comment on {recipe_title}",
        "template": "emails/recipe_commented.html",
    },
    "RECIPE_SHARED": {
        "subject": "{actor_name} shared a recipe with you",
        "template": "emails/recipe_shared.html",
    },
    "RECIPE_COLLECTED": {
        "subject": "Your recipe was added to a collection",
        "template": "emails/recipe_collected.html",
    },
    "RECIPE_RATED": {
        "subject": "Your recipe was rated",
        "template": "emails/recipe_rated.html",
    },
    "RECIPE_FEATURED": {
        "subject": "Your recipe has been featured!",
        "template": "emails/recipe_featured.html",
    },
    "RECIPE_TRENDING": {
        "subject": "Your recipe is trending!",
        "template": "emails/recipe_trending.html",
    },
    # Social events
    "NEW_FOLLOWER": {
        "subject": "{actor_name} started following you",
        "template": "emails/new_follower.html",
    },
    "MENTION": {
        "subject": "{actor_name} mentioned you",
        "template": "emails/mention.html",
    },
    "COLLECTION_INVITE": {
        "subject": "You've been invited to a collection",
        "template": "emails/notification.html",
    },
    # System events
    "WELCOME": {
        "subject": "Welcome to Recipe App!",
        "template": "emails/welcome.html",
    },
    "PASSWORD_RESET": {
        "subject": "Reset your password",
        "template": "emails/password_reset.html",
    },
    "PASSWORD_CHANGED": {
        "subject": "Your password was changed",
        "template": "emails/password_changed.html",
    },
    "EMAIL_CHANGED": {
        "subject": "Your email address was updated",
        "template": "emails/email_changed.html",
    },
    "MAINTENANCE": {
        "subject": "Scheduled Maintenance Notice",
        "template": "emails/maintenance.html",
    },
    "SYSTEM_ALERT": {
        "subject": "System Alert",
        "template": "emails/notification.html",
    },
}


def get_email_template(category: str) -> EmailTemplateConfig:
    """Get email template configuration for a notification category.

    Args:
        category: The notification category.

    Returns:
        EmailTemplateConfig with subject and template path.

    Raises:
        KeyError: If category is not found in EMAIL_TEMPLATES.
    """
    return EMAIL_TEMPLATES[category]
