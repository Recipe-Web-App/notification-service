"""Django application configuration for core."""

import logging

from django.apps import AppConfig

from core.services import database_monitor, health_service

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    """Configuration class for the core application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self) -> None:
        """Initialize services when Django app is ready."""
        import core.signals  # noqa: PLC0415

        del core.signals

        health_service.set_database_monitor(database_monitor)
        logger.info("Database monitoring service initialized")
