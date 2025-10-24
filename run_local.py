#!/usr/bin/env python
"""Script to run the Django development server."""

import os
import sys

from django.core.management import execute_from_command_line


def main():
    """Run the Django development server."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "notification_service.settings")
    execute_from_command_line([sys.argv[0], "runserver"])


if __name__ == "__main__":
    main()
