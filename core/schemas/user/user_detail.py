"""Detailed user schema with extended user information."""

from datetime import datetime
from typing import Any, ClassVar

from pydantic import Field

from core.schemas.user.user_base import UserBase


class UserDetail(UserBase):
    """Extended user schema with full user profile information.

    Includes all fields from UserBase plus additional profile details.
    """

    role: str = Field(..., description="User role (ADMIN or USER)")
    full_name: str | None = Field(None, max_length=255, description="User's full name")
    bio: str | None = Field(None, description="User biography/description")
    is_active: bool = Field(default=True, description="Whether user account is active")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        """Pydantic model configuration."""

        from_attributes = True  # Allow creation from ORM models
        json_schema_extra: ClassVar[dict[str, dict[str, Any]]] = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "username": "johndoe",
                "email": "john.doe@example.com",
                "role": "USER",
                "full_name": "John Doe",
                "bio": "Food enthusiast and home chef",
                "is_active": True,
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-20T14:45:00Z",
            }
        }
