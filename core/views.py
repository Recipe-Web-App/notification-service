"""API views for core application."""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.services import health_service


class HealthCheckView(APIView):
    """Simple health check endpoint.

    This endpoint is exempt from authentication to allow Kubernetes probes
    and monitoring systems to check service health.
    """

    def __init__(self, **kwargs):
        """Initialize view with authentication exemptions.

        Exempt from authentication - health checks must be accessible without auth.

        Args:
            **kwargs: Keyword arguments passed to parent class
        """
        super().__init__(**kwargs)
        self.authentication_classes = []
        self.permission_classes = [AllowAny]

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

    This endpoint is exempt from authentication to allow Kubernetes probes.
    """

    def __init__(self, **kwargs):
        """Initialize view with authentication exemptions.

        Exempt from authentication - health checks must be accessible without auth.

        Args:
            **kwargs: Keyword arguments passed to parent class
        """
        super().__init__(**kwargs)
        self.authentication_classes = []
        self.permission_classes = [AllowAny]

    def get(self, _request):
        """Handle GET request for liveness check.

        Args:
            _request: HTTP request object (unused).

        Returns:
            Response object with status OK if service is alive.
        """
        liveness = health_service.get_liveness_status()
        return Response(liveness.model_dump(), status=status.HTTP_200_OK)


class ReadinessCheckView(APIView):
    """Readiness probe endpoint for Kubernetes.

    Returns 200 if the service is ready to serve traffic.
    Returns degraded status (200 OK) when database is unavailable,
    allowing service to stay alive while background reconnection continues.

    This endpoint is exempt from authentication to allow Kubernetes probes.
    """

    def __init__(self, **kwargs):
        """Initialize view with authentication exemptions.

        Exempt from authentication - health checks must be accessible without auth.

        Args:
            **kwargs: Keyword arguments passed to parent class
        """
        super().__init__(**kwargs)
        self.authentication_classes = []
        self.permission_classes = [AllowAny]

    def get(self, _request):
        """Handle GET request for readiness check.

        Args:
            _request: HTTP request object (unused).

        Returns:
            Response object with status OK if service is ready or degraded.
        """
        readiness = health_service.get_readiness_status()
        return Response(readiness.model_dump(), status=status.HTTP_200_OK)
