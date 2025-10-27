"""Conditional database monitoring with exponential backoff."""

import logging
import threading
import time

from django.db import connection
from django.db.utils import OperationalError

logger = logging.getLogger(__name__)


class DatabaseMonitor:
    """Conditional database monitoring service.

    Only runs when database is unhealthy. Stops automatically when connection
    recovers. Uses exponential backoff for reconnection attempts.
    """

    def __init__(
        self,
        check_interval_seconds: int = 30,
        max_consecutive_failures: int = 3,
    ) -> None:
        """Initialize the database monitor.

        Args:
            check_interval_seconds: Base interval between health checks
            max_consecutive_failures: Failures before exponential backoff starts
        """
        self.check_interval_seconds = check_interval_seconds
        self.max_consecutive_failures = max_consecutive_failures
        self._is_running = False
        self._monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._consecutive_failures = 0
        self._last_check_time: float | None = None

    def start_monitoring(self) -> None:
        """Start the monitoring thread if not already running."""
        if self._is_running:
            logger.debug("Database monitor already running")
            return

        self._is_running = True
        self._stop_event.clear()
        self._consecutive_failures = 0

        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="DatabaseMonitor",
            daemon=True,
        )
        self._monitor_thread.start()
        logger.info("Database monitor started")

    def stop_monitoring(self) -> None:
        """Stop the monitoring thread."""
        if not self._is_running:
            return

        self._is_running = False
        self._stop_event.set()

        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=5.0)
            self._monitor_thread = None

        logger.info("Database monitor stopped")

    def _monitor_loop(self) -> None:
        """Main monitoring loop with exponential backoff."""
        while not self._stop_event.is_set():
            self._last_check_time = time.time()

            # Check database health
            is_healthy = self._check_database_connection()

            if is_healthy:
                # Connection recovered - stop monitoring
                logger.info(
                    "Database connection recovered after %d failures",
                    self._consecutive_failures,
                )
                self._consecutive_failures = 0
                self._is_running = False
                break

            # Still unhealthy - increment failure counter
            self._consecutive_failures += 1

            # Log periodic updates for prolonged outages
            if self._consecutive_failures % 10 == 0:
                elapsed_minutes = (
                    self._consecutive_failures * self.check_interval_seconds
                ) // 60
                logger.warning(
                    "Database still unavailable after ~%d minutes (%d attempts)",
                    elapsed_minutes,
                    self._consecutive_failures,
                )

            # Calculate next check interval with exponential backoff
            interval = self._calculate_backoff_interval()
            logger.debug(
                "Next database check in %d seconds (failure #%d)",
                interval,
                self._consecutive_failures,
            )

            # Wait for next check (or stop signal)
            self._stop_event.wait(timeout=interval)

    def _check_database_connection(self) -> bool:
        """Check if database connection is healthy.

        Returns:
            True if database is healthy, False otherwise
        """
        try:
            connection.ensure_connection()
            return True
        except OperationalError:
            return False
        except Exception as e:
            logger.error("Unexpected error checking database: %s", e)
            return False

    def _calculate_backoff_interval(self) -> int:
        """Calculate next check interval with exponential backoff.

        Returns:
            Number of seconds until next check (capped at 300 seconds)
        """
        if self._consecutive_failures <= self.max_consecutive_failures:
            return self.check_interval_seconds

        # Exponential backoff: 2^(failures - max_failures) * base_interval
        # Capped at 10x multiplier (300 seconds with 30s base)
        backoff_multiplier = min(
            2 ** (self._consecutive_failures - self.max_consecutive_failures),
            10,
        )
        return int(min(self.check_interval_seconds * backoff_multiplier, 300))

    @property
    def is_monitoring(self) -> bool:
        """Check if monitoring is currently active.

        Returns:
            True if monitoring thread is running
        """
        return self._is_running

    @property
    def consecutive_failures(self) -> int:
        """Get the current consecutive failure count.

        Returns:
            Number of consecutive failures
        """
        return self._consecutive_failures


# Global database monitor instance
database_monitor = DatabaseMonitor()
