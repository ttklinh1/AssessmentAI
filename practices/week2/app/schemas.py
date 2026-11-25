from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class MeetingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transcript: str = Field(min_length=1, description="Full meeting transcript")


class Decision(BaseModel):
    decision: str = Field(min_length=1)


class ActionItem(BaseModel):
    owner: Optional[str] = None
    action: str = Field(min_length=1)
    # Keep dates as strings so missing dates are null and no date is invented.
    due_date: Optional[str] = None


class MeetingAnalysis(BaseModel):
    summary: str = Field(min_length=1)
    decisions: list[Decision] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
