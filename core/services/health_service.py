"""Health check service with caching and database monitoring."""

import logging
import time

from django.core.cache import cache
from django.db import connection
from django.db.utils import OperationalError

from core.enums import HealthStatus
from core.schemas.health import (
    DependencyHealth,
    LivenessResponse,
    ReadinessResponse,
)
from core.services.database_monitor import DatabaseMonitor

logger = logging.getLogger(__name__)


class HealthService:
    """Service for performing health checks with caching."""

    def __init__(self, cache_ttl_seconds: float = 5.0) -> None:
        """Initialize the health service.

        Args:
            cache_ttl_seconds: Time to live for cached health check results
        """
        self.cache_ttl_seconds = cache_ttl_seconds
        self._db_health_cache: DependencyHealth | None = None
        self._db_health_cache_time: float = 0.0
        self._redis_health_cache: DependencyHealth | None = None
        self._redis_health_cache_time: float = 0.0
        self._database_monitor: DatabaseMonitor | None = None

    def set_database_monitor(self, monitor: DatabaseMonitor) -> None:
        """Set the database monitor for conditional polling.

        Args:
            monitor: The database monitor instance
        """
        self._database_monitor = monitor

    def get_liveness_status(self) -> LivenessResponse:
        """Get liveness status (always returns alive).

        Returns:
            LivenessResponse with status "alive"
        """
        return LivenessResponse(status="alive")

    def get_readiness_status(self) -> ReadinessResponse:
        """Get readiness status with database and Redis health checks.

        Returns degraded (ready=True, degraded=True) when dependencies are down,
        allowing the service to remain deployable while reconnection continues.

        Returns:
            ReadinessResponse with overall status and dependency health
        """
        # Check all dependency health
        db_health = self.check_database_health()
        redis_health = self.check_redis_health()

        # Determine overall service status
        dependencies = {"database": db_health, "redis": redis_health}

        # Service is degraded if any dependency is unhealthy
        all_healthy = db_health.healthy and redis_health.healthy

        if all_healthy:
            service_ready = True
            service_degraded = False
            service_status = "ready"
        else:
            # Service is degraded but still ready to accept requests
            service_ready = True
            service_degraded = True
            service_status = "degraded"

        return ReadinessResponse(
            ready=service_ready,
            status=service_status,
            degraded=service_degraded,
            dependencies=dependencies,
        )

    def check_database_health(self) -> DependencyHealth:
        """Check database connectivity with caching.

        Uses Django's ensure_connection() for efficient socket validation
        without executing queries. Results are cached for cache_ttl_seconds.

        When database transitions from healthy to unhealthy, starts the
        database monitor for conditional background polling.

        Returns:
            DependencyHealth with database status
        """
        # Check if cached result is still valid
        current_time = time.time()
        if (
            self._db_health_cache is not None
            and (current_time - self._db_health_cache_time) < self.cache_ttl_seconds
        ):
            return self._db_health_cache

        # Perform fresh health check
        start_time = time.perf_counter()
        try:
            # Validate database connection (most efficient - no query execution)
            connection.ensure_connection()

            response_time_ms = (time.perf_counter() - start_time) * 1000
            new_health = DependencyHealth(
                healthy=True,
                status=HealthStatus.HEALTHY,
                message="Database connection successful",
                response_time_ms=response_time_ms,
            )

            # If we were unhealthy and now healthy, stop monitoring
            if (
                self._db_health_cache is not None
                and not self._db_health_cache.healthy
                and self._database_monitor is not None
            ):
                logger.info("Database connection recovered")
                self._database_monitor.stop_monitoring()

        except OperationalError as e:
            response_time_ms = (time.perf_counter() - start_time) * 1000
            new_health = DependencyHealth(
                healthy=False,
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {e!s}",
                response_time_ms=response_time_ms,
            )

            # If we just became unhealthy, start monitoring
            if (
                self._db_health_cache is None or self._db_health_cache.healthy
            ) and self._database_monitor is not None:
                logger.warning("Database connection lost, starting background monitor")
                self._database_monitor.start_monitoring()

        except Exception as e:
            response_time_ms = (time.perf_counter() - start_time) * 1000
            new_health = DependencyHealth(
                healthy=False,
                status=HealthStatus.ERROR,
                message=f"Unexpected error checking database: {e!s}",
                response_time_ms=response_time_ms,
            )

            # If we just became unhealthy, start monitoring
            if (
                self._db_health_cache is None or self._db_health_cache.healthy
            ) and self._database_monitor is not None:
                logger.error(
                    "Unexpected error checking database, starting background monitor"
                )
                self._database_monitor.start_monitoring()

        # Update cache
        self._db_health_cache = new_health
        self._db_health_cache_time = current_time

        return new_health

    def check_redis_health(self) -> DependencyHealth:
        """Check Redis connectivity with caching.

        Tests Redis connection by attempting a simple operation.
        Results are cached for cache_ttl_seconds.

        Returns:
            DependencyHealth with Redis status
        """
        # Check if cached result is still valid
        current_time = time.time()
        if (
            self._redis_health_cache is not None
            and (current_time - self._redis_health_cache_time) < self.cache_ttl_seconds
        ):
            return self._redis_health_cache

        # Perform fresh health check
        start_time = time.perf_counter()
        try:
            # Test Redis connection with a simple operation
            test_key = "__health_check__"
            cache.set(test_key, "ok", timeout=1)
            result = cache.get(test_key)

            if result == "ok":
                response_time_ms = (time.perf_counter() - start_time) * 1000
                new_health = DependencyHealth(
                    healthy=True,
                    status=HealthStatus.HEALTHY,
                    message="Redis connection successful",
                    response_time_ms=response_time_ms,
                )
            else:
                response_time_ms = (time.perf_counter() - start_time) * 1000
                new_health = DependencyHealth(
                    healthy=False,
                    status=HealthStatus.UNHEALTHY,
                    message="Redis health check failed: unexpected result",
                    response_time_ms=response_time_ms,
                )

        except Exception as e:
            response_time_ms = (time.perf_counter() - start_time) * 1000
            new_health = DependencyHealth(
                healthy=False,
                status=HealthStatus.ERROR,
                message=f"Redis connection failed: {e!s}",
                response_time_ms=response_time_ms,
            )
            logger.warning(f"Redis health check failed: {e}")

        # Update cache
        self._redis_health_cache = new_health
        self._redis_health_cache_time = current_time

        return new_health


# Global health service instance
health_service = HealthService()
