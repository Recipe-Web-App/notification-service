"""Base pydantic model for centralized configuration of schema definitions."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class BaseSchemaModel(BaseModel):
    """Base pydantic model for centralized configuration of schema definitions.

    This base model sets common configurations for all schema models
    in the application, ensuring consistency and reducing redundancy.
    """

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True,
        use_enum_values=True,
        extra="ignore",
        str_strip_whitespace=True,
    )
