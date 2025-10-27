"""Custom structlog processors for request context and service metadata."""

import os
import threading

from colorama import Fore, Style, init
from structlog.typing import EventDict, WrappedLogger

from core.logging.context import get_request_id


def add_request_context(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Add request ID from thread-local context to log events.

    This processor integrates with the existing RequestIDMiddleware to
    automatically include the request_id in all log events.

    Args:
        logger: The wrapped logger instance.
        method_name: The name of the method called on the logger.
        event_dict: The event dictionary to be logged.

    Returns:
        The event dictionary with request_id added if available.
    """
    request_id = get_request_id()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict


def add_service_context(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Add service metadata to all log events.

    Includes:
    - service_name: The name of the service
    - environment: The deployment environment (dev/staging/prod)

    Args:
        logger: The wrapped logger instance.
        method_name: The name of the method called on the logger.
        event_dict: The event dictionary to be logged.

    Returns:
        The event dictionary with service metadata added.
    """
    event_dict["service_name"] = os.getenv("SERVICE_NAME", "notification-service")
    event_dict["environment"] = os.getenv("ENVIRONMENT", "development")
    return event_dict


def add_process_info(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Add process and thread information to log events.

    Includes:
    - process_id: The current process ID
    - thread_id: The current thread ID

    Args:
        _logger: The wrapped logger instance (unused, required by structlog interface).
        _method_name: The name of the method called on the logger (unused).
        event_dict: The event dictionary to be logged.

    Returns:
        The event dictionary with process/thread info added.
    """
    event_dict["process_id"] = os.getpid()
    event_dict["thread_id"] = threading.get_ident()
    return event_dict


def console_renderer(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> str:
    """Render log events as colored, pretty-printed strings for console output.

    Format: [LEVEL] timestamp | request_id | logger_name | message

    Uses colors:
    - DEBUG: Cyan
    - INFO: Green
    - WARNING: Yellow
    - ERROR: Red
    - CRITICAL: Red + Bold

    Args:
        _logger: The wrapped logger instance (unused, required by structlog interface).
        _method_name: The name of the method called on the logger (unused).
        event_dict: The event dictionary to be logged.

    Returns:
        A formatted, colored string for console output.
    """
    # Initialize colorama for cross-platform color support
    init(autoreset=True)

    # Extract fields
    level = event_dict.get("level", "INFO").upper()
    timestamp = event_dict.get("timestamp", "")
    request_id = event_dict.get("request_id", "no-request-id")
    logger_name = event_dict.get("logger", "root")
    message = event_dict.get("event", "")

    # Color mapping for log levels
    level_colors = {
        "DEBUG": Fore.CYAN,
        "INFO": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "CRITICAL": Fore.RED + Style.BRIGHT,
    }

    # Get color for level, default to white
    level_color = level_colors.get(level, Fore.WHITE)

    # Format the output
    # [LEVEL] timestamp | request_id | logger_name | message
    formatted = (
        f"{level_color}[{level:<8}]{Style.RESET_ALL} "
        f"{Fore.WHITE}{timestamp}{Style.RESET_ALL} | "
        f"{Fore.MAGENTA}{request_id}{Style.RESET_ALL} | "
        f"{Fore.BLUE}{logger_name}{Style.RESET_ALL} | "
        f"{message}"
    )

    # Add any additional context (excluding fields we already displayed)
    excluded_fields = {
        "level",
        "timestamp",
        "request_id",
        "logger",
        "event",
        # Exclude process/thread/service metadata from console for cleanliness
        "process_id",
        "thread_id",
        "service_name",
        "service_version",
        "environment",
    }

    extra_fields = {k: v for k, v in event_dict.items() if k not in excluded_fields}

    if extra_fields:
        extra_str = " ".join(f"{k}={v}" for k, v in extra_fields.items())
        formatted += f" {Fore.YELLOW}{extra_str}{Style.RESET_ALL}"

    return formatted
