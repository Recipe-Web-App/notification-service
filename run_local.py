#!/usr/bin/env python
"""Script to run the Django development server."""

import os
import sys

from django.core.management import execute_from_command_line


def main():
    """Run the Django development server.

    Uses custom 'runlocal' command that skips migration checks,
    allowing startup without database connection (degraded mode).
    """
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "notification_service.settings")
    execute_from_command_line([sys.argv[0], "runlocal"])


if __name__ == "__main__":
    main()
