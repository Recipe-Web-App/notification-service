"""Production server startup script for notification service.

This module provides the entry point for starting the Django application
with Gunicorn in production environments (Docker containers, Kubernetes).
"""

import sys

from gunicorn.app.wsgiapp import run


def main():
    """Start the notification service using Gunicorn.

    Configures and launches Gunicorn with production-ready settings:
    - Binds to 0.0.0.0:8000 for container accessibility
    - Uses 4 worker processes for concurrent request handling
    - 2 threads per worker for improved throughput
    - 60-second timeout for long-running requests
    - Logs to stdout/stderr for container log aggregation
    """
    sys.argv = [
        "gunicorn",
        "notification_service.wsgi:application",
        "--bind",
        "0.0.0.0:8000",
        "--workers",
        "4",
        "--threads",
        "2",
        "--timeout",
        "60",
        "--access-logfile",
        "-",
        "--error-logfile",
        "-",
    ]
    run()


if __name__ == "__main__":
    main()
