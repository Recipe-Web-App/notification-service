"""Schema for template information."""

from pydantic import ConfigDict, Field

from core.schemas.base_schema_model import BaseSchemaModel


class TemplateInfo(BaseSchemaModel):
    """Schema for notification template information.

    Matches the OpenAPI specification for TemplateInfo.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "template_type": "recipe_published",
                "display_name": "Recipe Published",
                "description": "Notify followers when a new recipe is published",
                "required_fields": ["recipient_ids", "recipe_id"],
                "endpoint": "/notifications/recipe-published",
            }
        }
    )

    template_type: str = Field(..., description="Template type identifier")
    display_name: str = Field(..., description="Human-readable template name")
    description: str = Field(..., description="Template description")
    required_fields: list[str] = Field(
        ..., description="Required fields for this template"
    )
    endpoint: str = Field(..., description="API endpoint for this template")
