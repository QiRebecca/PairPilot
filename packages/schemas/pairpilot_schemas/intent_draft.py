"""Structured output contract for Qi Agent's intent-post interpretation."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pairpilot_schemas.domain import FieldSource


class AgentOnlyDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quiet_overnight_compatibility_importance: str = Field(
        pattern=r"^(low|medium|high)$"
    )
    partial_date_overlap_allowed: bool
    maximum_additional_cost_usd: int = Field(ge=0, le=10_000)


class DraftFieldProvenance(BaseModel):
    """Required origin marker for every core field in a draft."""

    model_config = ConfigDict(extra="forbid")

    intent_type: FieldSource
    public_title: FieldSource
    public_summary: FieldSource
    event: FieldSource
    location: FieldSource
    date_start: FieldSource
    date_end: FieldSource
    roommate_gender_preference: FieldSource
    maximum_additional_cost_usd: FieldSource
    partial_date_overlap_allowed: FieldSource
    quiet_overnight_compatibility: FieldSource


class IntentDraft(BaseModel):
    """Editable draft; it contains no raw protected-memory value."""

    model_config = ConfigDict(extra="forbid")

    intent_type: str = Field(pattern=r"^conference_room_share$")
    public_title: str = Field(min_length=1, max_length=120)
    public_summary: str = Field(min_length=1, max_length=600)
    event: str = Field(min_length=1, max_length=80)
    location: str = Field(min_length=1, max_length=120)
    date_start: date
    date_end: date
    roommate_gender_preference: str = Field(min_length=1, max_length=40)
    public_requirements: list[str] = Field(default_factory=list, max_length=12)
    agent_only: AgentOnlyDraft
    field_provenance: DraftFieldProvenance
    uncertainties: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def dates_and_provenance_are_complete(self) -> "IntentDraft":
        if self.date_end <= self.date_start:
            raise ValueError("draft end date must follow start date")
        return self
