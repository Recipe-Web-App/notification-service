"""Django signals for notification triggers."""

from core.signals.user_signals import send_welcome_email

__all__ = ["send_welcome_email"]
