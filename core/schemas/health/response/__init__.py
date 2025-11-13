"""Health response schemas."""

from core.schemas.health.response.liveness_response import LivenessResponse
from core.schemas.health.response.readiness_response import ReadinessResponse

__all__ = ["LivenessResponse", "ReadinessResponse"]
