from uuid import UUID

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel


class NotificationCreated(BaseSchemaModel):
    """Schema for individual notification in batch response."""

    notification_id: UUID = Field(..., description="UUID of the created notification")
    recipient_id: UUID = Field(..., description="UUID of the recipient user")
