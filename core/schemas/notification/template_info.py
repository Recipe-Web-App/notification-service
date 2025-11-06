"""Schema for template information."""

from pydantic import BaseModel, Field


class TemplateInfo(BaseModel):
    """Schema for notification template information.

    Matches the OpenAPI specification for TemplateInfo.
    """

    template_type: str = Field(..., description="Template type identifier")
    display_name: str = Field(..., description="Human-readable template name")
    description: str = Field(..., description="Template description")
    required_fields: list[str] = Field(
        ..., description="Required fields for this template"
    )
    endpoint: str = Field(..., description="API endpoint for this template")

    model_config = {
        "json_schema_extra": {
            "example": {
                "template_type": "recipe_published",
                "display_name": "Recipe Published",
                "description": "Notify followers when a new recipe is published",
                "required_fields": ["recipient_ids", "recipe_id"],
                "endpoint": "/notifications/recipe-published",
            }
        }
    }


class TemplateListResponse(BaseModel):
    """Schema for template list response."""

    templates: list[TemplateInfo] = Field(
        ..., description="List of available templates"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "templates": [
                    {
                        "template_type": "recipe_published",
                        "display_name": "Recipe Published",
                        "description": (
                            "Notify followers when a new recipe is published"
                        ),
                        "required_fields": ["recipient_ids", "recipe_id"],
                        "endpoint": "/notifications/recipe-published",
                    }
                ]
            }
        }
    }
