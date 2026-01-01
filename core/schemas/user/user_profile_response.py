"""User profile response schema from user-management service."""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel


class UserProfileResponse(BaseSchemaModel):
    """User profile response from user-management service.

    This schema matches the GET /user-management/users/{user_id}/profile response.
    Includes email when the requester has appropriate access (service-to-service auth).
    """

    # Required fields
    user_id: UUID = Field(
        ..., alias="userId", description="Unique identifier for the user"
    )
    username: str = Field(..., description="Username for the user account")
    is_active: bool = Field(
        ..., alias="isActive", description="Whether the user account is active"
    )
    created_at: datetime = Field(
        ..., alias="createdAt", description="Timestamp when user account was created"
    )
    updated_at: datetime = Field(
        ...,
        alias="updatedAt",
        description="Timestamp when user account was last updated",
    )

    # Optional fields
    email: str | None = Field(
        None,
        description="Email address (included if contact info is visible)",
    )
    full_name: str | None = Field(
        None, alias="fullName", description="Full name of the user"
    )
    bio: str | None = Field(None, description="User's biography or description")
