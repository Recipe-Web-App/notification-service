"""Services for the core app."""

from core.services.database_monitor import DatabaseMonitor, database_monitor
from core.services.email_service import EmailService
from core.services.health_service import HealthService, health_service

# Note: UserNotificationService is not exported here to avoid circular imports
# during Django app initialization. Import directly from the module.

__all__ = [
    "DatabaseMonitor",
    "EmailService",
    "HealthService",
    "database_monitor",
    "health_service",
]
