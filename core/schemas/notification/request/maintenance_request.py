"""Request schema for maintenance notifications."""

from datetime import datetime

from pydantic import ConfigDict, Field, model_validator

from core.schemas.base_schema_model import BaseSchemaModel


class MaintenanceRequest(BaseSchemaModel):
    """Request schema for sending maintenance notifications.

    Broadcasts maintenance window notifications to users or admins.
    Recipients are automatically discovered based on admin_only flag.

    Attributes:
        maintenance_start: Scheduled start time of maintenance window (ISO 8601).
        maintenance_end: Scheduled end time of maintenance window (ISO 8601).
        description: Description of maintenance work and expected impact
            (max 1000 chars).
        admin_only: If True, send only to admins. If False, send to all users
            and admins.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "adminOnly": False,
                "maintenance_start": "2025-11-15T02:00:00Z",
                "maintenance_end": "2025-11-15T06:00:00Z",
                "description": (
                    "Scheduled database maintenance. "
                    "The platform will be unavailable during this time."
                ),
            }
        }
    )

    maintenance_start: datetime = Field(
        ...,
        description="Scheduled start time of maintenance window (ISO 8601)",
    )
    maintenance_end: datetime = Field(
        ...,
        description="Scheduled end time of maintenance window (ISO 8601)",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Description of maintenance work and expected impact",
    )
    admin_only: bool = Field(
        default=False,
        description=(
            "If True, send only to admins. If False, send to all users and admins."
        ),
    )

    @model_validator(mode="after")
    def validate_maintenance_window(self):
        """Validate that maintenance_end is after maintenance_start.

        Returns:
            The validated model instance

        Raises:
            ValueError: If maintenance_end is not after maintenance_start
        """
        if self.maintenance_end <= self.maintenance_start:
            raise ValueError("maintenance_end must be after maintenance_start")
        return self
