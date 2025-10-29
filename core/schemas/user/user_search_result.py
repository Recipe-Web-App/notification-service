"""User search result schema from user-management service."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserSearchResult(BaseModel):
    """User search result data transfer object from user-management service.

    This schema matches the GET /user-management/users/{user_id} response.
    Represents public profile information for a user.
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
    full_name: str | None = Field(
        None, alias="fullName", description="Full name of the user"
    )

    class Config:
        """Pydantic configuration."""

        populate_by_name = True
