"""Template registry constants.

This module defines all available notification templates with their metadata.
Used by the template listing endpoint and for template validation.
"""

TEMPLATE_REGISTRY = [
    {
        "template_type": "recipe_published",
        "display_name": "Recipe Published",
        "description": "Notify followers when a new recipe is published",
        "required_fields": ["recipient_ids", "recipe_id"],
        "endpoint": "/notifications/recipe-published",
    },
    {
        "template_type": "recipe_liked",
        "display_name": "Recipe Liked",
        "description": "Notify recipe author when someone likes their recipe",
        "required_fields": ["recipient_ids", "recipe_id", "liker_id"],
        "endpoint": "/notifications/recipe-liked",
    },
    {
        "template_type": "recipe_commented",
        "display_name": "Recipe Commented",
        "description": "Notify recipe author when someone comments",
        "required_fields": ["recipient_ids", "comment_id"],
        "endpoint": "/notifications/recipe-commented",
    },
    {
        "template_type": "new_follower",
        "display_name": "New Follower",
        "description": "Notify user about new follower",
        "required_fields": ["recipient_ids", "follower_id"],
        "endpoint": "/notifications/new-follower",
    },
    {
        "template_type": "mention",
        "display_name": "Mention",
        "description": "Notify user when mentioned in a comment",
        "required_fields": ["recipient_ids", "comment_id"],
        "endpoint": "/notifications/mention",
    },
    {
        "template_type": "password_reset",
        "display_name": "Password Reset",
        "description": "Send password reset link",
        "required_fields": ["recipient_ids", "reset_token", "expiry_hours"],
        "endpoint": "/notifications/password-reset",
    },
    {
        "template_type": "recipe_trending",
        "display_name": "Recipe Trending",
        "description": "Notify recipe author when their recipe is trending",
        "required_fields": ["recipient_ids", "recipe_id"],
        "endpoint": "/notifications/recipe-trending",
    },
    {
        "template_type": "email_changed",
        "display_name": "Email Changed",
        "description": "Security notification for email address change",
        "required_fields": ["recipient_ids", "old_email", "new_email"],
        "endpoint": "/notifications/email-changed",
    },
    {
        "template_type": "password_changed",
        "display_name": "Password Changed",
        "description": "Security notification for password change",
        "required_fields": ["recipient_ids"],
        "endpoint": "/notifications/password-changed",
    },
]
