"""Request schema for welcoming new users to the system."""

from uuid import UUID

from pydantic import BaseModel, Field


class WelcomeRequest(BaseModel):
    """Request schema for sending welcome notifications to new users.

    This schema validates requests for sending welcome emails to newly
    registered users. Supports both single and batch recipients.
    """

    recipient_ids: list[UUID] = Field(
        ...,
        min_length=1,
        description="List of recipient user IDs to send welcome notifications to",
    )
