"""Structlog configuration for dual output: JSON files and colored console."""

import logging
import logging.handlers
import os
import time
from pathlib import Path

import structlog

from core.logging.processors import (
    add_process_info,
    add_request_context,
    add_service_context,
    console_renderer,
)


def setup_logging() -> None:
    """Configure structlog with dual output: JSON file logs and colored console logs.

    File Output:
    - JSON formatted with all metadata
    - Rotating file handler (100MB per file, 10 days retention)
    - Includes: timestamp, level, logger, message, request_id, service_name,
      environment, process/thread info

    Console Output:
    - Pretty-printed with colors
    - Format: [LEVEL] timestamp | request_id | logger_name | message
    - Always enabled (even in production)

    Environment Variables:
    - LOG_FILE_PATH: Path to log file (default: ./logs/notification-service.log)
    - LOG_LEVEL: Logging level (default: INFO)
    - SERVICE_NAME: Service name for metadata (default: notification-service)
    - ENVIRONMENT: Deployment environment (default: development)
    """
    # Get configuration from environment
    log_file_path = os.getenv("LOG_FILE_PATH", "./logs/notification-service.log")
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Ensure log directory exists
    log_dir = Path(log_file_path).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Configure standard library logging
    # This ensures compatibility with Django and other libraries
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level, logging.INFO),
        handlers=[],  # We'll add handlers below
    )

    # Create rotating file handler for JSON logs
    # 100MB per file, 10 days retention (assuming ~240 files for 10 days at high load)
    # Conservative: 100MB * 240 = 24GB max disk usage
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file_path,
        maxBytes=100 * 1024 * 1024,  # 100MB
        backupCount=240,  # ~10 days at high load (1 file per hour = 240 files)
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, log_level, logging.INFO))

    # Create console handler for colored output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level, logging.INFO))

    # Configure structlog
    structlog.configure(
        processors=[
            # Add log level to event dict
            structlog.stdlib.add_log_level,
            # Add logger name to event dict
            structlog.stdlib.add_logger_name,
            # Add timestamp in ISO8601 format with milliseconds
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            # Add stack info for exceptions
            structlog.processors.StackInfoRenderer(),
            # Format exceptions
            structlog.processors.format_exc_info,
            # Add custom context processors
            add_request_context,  # Adds request_id from thread-local
            add_service_context,  # Adds service_name, version, environment
            add_process_info,  # Adds process_id, thread_id
            # Final processor: route to appropriate renderer based on handler
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        # Use structlog's logger factory for stdlib compatibility
        logger_factory=structlog.stdlib.LoggerFactory(),
        # Use structlog's bound logger for better API
        wrapper_class=structlog.stdlib.BoundLogger,
        # Cache logger instances for performance
        cache_logger_on_first_use=True,
    )

    # Configure formatters for each handler
    # File handler: JSON formatter with all metadata
    file_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=[
                # For logs from libraries that don't use structlog
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.TimeStamper(fmt="iso", utc=True),
                add_request_context,
                add_service_context,
                add_process_info,
            ],
        )
    )

    # Console handler: Colored pretty-printer
    console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=console_renderer,
            foreign_pre_chain=[
                # For logs from libraries that don't use structlog
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.TimeStamper(fmt="iso", utc=True),
                add_request_context,
            ],
        )
    )

    # Add handlers to root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()  # Remove any existing handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Log startup message
    logger = structlog.get_logger(__name__)
    logger.info(
        "Logging configured",
        log_file=log_file_path,
        log_level=log_level,
        max_file_size_mb=100,
        retention_days=10,
    )


def cleanup_old_logs(
    log_file_path: str | None = None, retention_days: int = 10
) -> None:
    """Remove log files older than the retention period.

    This function provides manual cleanup in addition to the rotating handler's
    automatic cleanup. Useful for cron jobs or manual maintenance.

    Args:
        log_file_path: Path to the main log file. If None, uses LOG_FILE_PATH env var.
        retention_days: Number of days to retain logs (default: 10).
    """
    if log_file_path is None:
        log_file_path = os.getenv("LOG_FILE_PATH", "./logs/notification-service.log")

    log_dir = Path(log_file_path).parent
    log_name = Path(log_file_path).name

    # Find all log files (including rotated ones like app.log.1, app.log.2, etc.)
    log_files = list(log_dir.glob(f"{log_name}*"))

    current_time = time.time()
    retention_seconds = retention_days * 24 * 60 * 60

    deleted_count = 0
    for log_file in log_files:
        # Skip the main log file
        if log_file.name == log_name:
            continue

        # Check file age
        file_age = current_time - log_file.stat().st_mtime

        if file_age > retention_seconds:
            try:
                log_file.unlink()
                deleted_count += 1
            except OSError as e:
                logger = structlog.get_logger(__name__)
                logger.warning(
                    "Failed to delete old log file",
                    file=str(log_file),
                    error=str(e),
                )

    if deleted_count > 0:
        logger = structlog.get_logger(__name__)
        logger.info(
            "Cleaned up old log files",
            deleted_count=deleted_count,
            retention_days=retention_days,
        )
