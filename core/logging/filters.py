"""Logging filters for enriching log records with request context."""

import logging

from core.logging.context import get_request_id


class RequestIDFilter(logging.Filter):
    """Add request ID to log records.

    This filter injects the current request ID from thread-local storage
    into every log record, enabling correlation of logs across a single request.

    If no request ID is set, it uses 'N/A' as a placeholder.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add request_id attribute to the log record.

        Args:
            record: The log record to enrich.

        Returns:
            True to indicate the record should be logged.
        """
        record.request_id = get_request_id() or "N/A"
        return True
