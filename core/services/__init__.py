"""Services for the core app.

Note: UserNotificationService, notification_service, and notification_templates
are not exported here to avoid circular imports during Django app initialization.
Import directly from the module when needed.
"""

from core.services.database_monitor import DatabaseMonitor, database_monitor
from core.services.email_service import EmailService
from core.services.health_service import HealthService, health_service

__all__ = [
    "DatabaseMonitor",
    "EmailService",
    "HealthService",
    "database_monitor",
    "health_service",
]
