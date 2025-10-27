"""Custom runserver command that skips migration checks.

This allows the service to start without a database connection during
local development, enabling the degraded mode health check pattern.
"""

from django.core.management.commands.runserver import Command as RunServer


class Command(RunServer):
    """Custom runserver that skips migration checks.

    This service does not own the database schema, so migration checks
    are unnecessary and would require a database connection at startup.
    """

    help = "Start development server without migration checks"

    def check_migrations(self, *_args, **_kwargs):
        """Skip migration checks - this service doesn't own the schema."""
        self.stdout.write(
            self.style.WARNING(
                "Skipping migration checks (service does not own database schema)"
            )
        )
