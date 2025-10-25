"""API views for core application."""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """Simple health check endpoint."""

    def get(self, _request):
        """Handle GET request for health check.

        Args:
            _request: HTTP request object (unused).

        Returns:
            Response object with status OK.
        """
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class LivenessCheckView(APIView):
    """Liveness probe endpoint for Kubernetes.

    Returns 200 if the service is alive and running.
    This should not check external dependencies.
    """

    def get(self, _request):
        """Handle GET request for liveness check.

        Args:
            _request: HTTP request object (unused).

        Returns:
            Response object with status OK if service is alive.
        """
        return Response({"status": "alive"}, status=status.HTTP_200_OK)


class ReadinessCheckView(APIView):
    """Readiness probe endpoint for Kubernetes.

    Returns 200 if the service is ready to serve traffic.
    """

    def get(self, _request):
        """Handle GET request for readiness check.

        Args:
            _request: HTTP request object (unused).

        Returns:
            Response object with status OK if service is ready.
        """
        # TODO: Add database connectivity check when database is configured
        return Response(
            {"status": "ready"},
            status=status.HTTP_200_OK,
        )
