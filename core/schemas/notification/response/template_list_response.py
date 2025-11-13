"""Schema for template list response."""

from pydantic import ConfigDict, Field

from core.schemas.base_schema_model import BaseSchemaModel
from core.schemas.notification.template_info import TemplateInfo


class TemplateListResponse(BaseSchemaModel):
    """Schema for template list response."""

    model_config = ConfigDict(
        json_schema_extra={
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
    )

    templates: list[TemplateInfo] = Field(
        ..., description="List of available templates"
    )
