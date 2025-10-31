"""Base user schema for common user fields."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Base user schema with essential user information.

    Used for basic user identification and contact information,
    primarily for notification purposes.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "username": "johndoe",
                "email": "john.doe@example.com",
            }
        },
    )

    user_id: UUID = Field(..., description="Unique identifier for the user")
    username: str = Field(..., min_length=1, max_length=50, description="Username")
    email: EmailStr = Field(..., description="User's email address")
