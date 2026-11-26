from typing import Optional, List
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MeetingRequest(BaseModel):
    """Request schema for meeting analysis."""

    model_config = ConfigDict(extra="forbid")

    meeting_text: str = Field(
        ...,
        min_length=1,
        description="Meeting transcript to analyze."
    )

    @field_validator("meeting_text")
    @classmethod
    def validate_meeting_text(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("meeting_text cannot be empty.")

        return value


class ActionItem(BaseModel):
    """Schema for individual action items."""

    model_config = ConfigDict(extra="forbid")

    owner: Optional[str] = None

    action: str = Field(
        ...,
        min_length=1
    )

    due_date: Optional[str] = None

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, value):
        if value is not None:
            value = value.strip()

            if not value:
                raise ValueError(
                    "Owner must be a non-empty name or null."
                )

        return value

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, value):
        if value is None:
            return None

        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            raise ValueError(
                "due_date must use YYYY-MM-DD format."
            )

        if parsed.isoformat() != value:
            raise ValueError(
                "due_date must use YYYY-MM-DD format."
            )

        return value


class MeetingAnalysis(BaseModel):
    """Response schema for meeting analysis."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(
        ...,
        min_length=1
    )

    decisions: List[str] = Field(
        default_factory=list
    )

    actions: List[ActionItem] = Field(
        default_factory=list
    )

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("Summary cannot be empty.")

        return value
