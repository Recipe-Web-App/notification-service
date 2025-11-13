"""Date range for statistics."""

from pydantic import Field

from core.schemas.base_schema_model import BaseSchemaModel


class DateRange(BaseSchemaModel):
    """Date range for statistics."""

    start: str | None = Field(
        None, description="Start date in ISO 8601 format (or null if no data)"
    )
    end: str | None = Field(
        None, description="End date in ISO 8601 format (or null if no data)"
    )
