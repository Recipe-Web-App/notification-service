"""Request schema for bulk notification deletion."""

from uuid import UUID

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel


class NotificationDeleteRequest(BaseSchemaModel):
    """Request schema for bulk notification deletion.

    Used by the DELETE /notifications endpoint to soft-delete multiple
    notifications in a single request.
    """

    notification_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of notification IDs to delete (1-100)",
    )
