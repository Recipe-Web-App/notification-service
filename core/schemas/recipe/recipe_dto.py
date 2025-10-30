"""Recipe DTO schema from recipe-management service."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DifficultyLevel(str, Enum):
    """Recipe difficulty levels."""

    BEGINNER = "BEGINNER"
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    EXPERT = "EXPERT"


class RecipeDto(BaseModel):
    """Recipe data transfer object from recipe-management service.

    This schema matches the GET /recipes/{recipeId} response.
    Includes required fields and commonly used optional fields.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=False,
    )

    # Required fields
    recipe_id: int = Field(
        ..., alias="recipeId", description="Unique recipe identifier"
    )
    user_id: UUID = Field(
        ..., alias="userId", description="UUID of the user who created the recipe"
    )
    title: str = Field(..., min_length=1, max_length=200, description="Recipe title")
    servings: Decimal = Field(..., ge=0, description="Number of servings")
    created_at: datetime = Field(
        ..., alias="createdAt", description="Creation timestamp"
    )

    # Common optional fields
    description: str | None = Field(
        None, max_length=2000, description="Recipe description"
    )
    origin_url: str | None = Field(
        None, alias="originUrl", description="The origin URL of the recipe"
    )
    preparation_time: int | None = Field(
        None, alias="preparationTime", ge=0, description="Preparation time in minutes"
    )
    cooking_time: int | None = Field(
        None, alias="cookingTime", ge=0, description="Cooking time in minutes"
    )
    difficulty: DifficultyLevel | None = Field(
        None, description="Recipe difficulty level"
    )
    updated_at: datetime | None = Field(
        None, alias="updatedAt", description="Last update timestamp"
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate title is not empty after stripping."""
        if not v.strip():
            raise ValueError("Title cannot be empty or whitespace only")
        return v
