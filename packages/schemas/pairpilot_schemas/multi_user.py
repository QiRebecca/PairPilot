"""P0 contracts for PairPilot's authenticated multi-user production plane."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OnboardingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=60)
    timezone: str = Field(min_length=1, max_length=80)
    general_location: str = Field(min_length=1, max_length=120)
    language: str = Field(min_length=2, max_length=40)
    adult_confirmed: bool
    public_profile_visible: bool = True
    default_autonomy_mode: Literal["AGENT", "COPILOT", "HUMAN"] = "COPILOT"
    public_sharing_policy: str = Field(min_length=1, max_length=500)
    agent_sharing_policy: str = Field(min_length=1, max_length=500)
    always_ask_policy: str = Field(min_length=1, max_length=500)
    community_ids: list[str] = Field(
        default_factory=lambda: ["community_icml_seoul_2026"], max_length=20
    )
    default_public_visibility: Literal["COMMUNITY", "BROADER_NETWORK"] = "COMMUNITY"
    default_agent_visibility: Literal["MINIMUM_NECESSARY", "TASK_CONTEXT"] = (
        "MINIMUM_NECESSARY"
    )
    notification_preference: Literal["IN_APP", "IN_APP_AND_EMAIL", "NONE"] = "IN_APP"

    @model_validator(mode="after")
    def require_adult_confirmation(self) -> OnboardingInput:
        if not self.adult_confirmed:
            raise ValueError("adult confirmation is required for this beta")
        return self


class CreateUserTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=100)
    task_type: str = Field(pattern=r"^[A-Za-z0-9_]+$")
    goal: str = Field(min_length=20, max_length=2_000)
    event: str = Field(min_length=1, max_length=80)
    location: str = Field(min_length=1, max_length=120)
    date_start: date
    date_end: date
    public_requirements: list[str] = Field(default_factory=list, max_length=12)
    maximum_additional_cost_usd: int = Field(ge=0, le=10_000)
    partial_date_overlap_allowed: bool = True
    community_id: str = Field(
        default="community_icml_seoul_2026",
        pattern=r"^community_[a-z0-9_]+$",
    )

    @model_validator(mode="after")
    def validate_dates(self) -> CreateUserTaskInput:
        if self.date_end < self.date_start:
            raise ValueError("date_end must not precede date_start")
        return self


class PublishUserPostInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_title: str = Field(min_length=1, max_length=120)
    public_summary: str = Field(min_length=1, max_length=600)
    public_requirements: list[str] = Field(default_factory=list, max_length=12)


class HumanProposalDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_version: int = Field(ge=1)
    confirmation: str = Field(min_length=1, max_length=100)


class UserRoomMessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=4_000)
    authorship: Literal["HUMAN_WRITTEN", "AGENT_DRAFTED_HUMAN_APPROVED"] = (
        "HUMAN_WRITTEN"
    )
    idempotency_key: str = Field(min_length=8, max_length=100)


class BlockUserInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_agent_id: str = Field(pattern=r"^agent_[a-f0-9]{24}$")
    reason: str | None = Field(default=None, max_length=300)


class ReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: Literal["POST", "USER", "MESSAGE"]
    target_id: str = Field(min_length=1, max_length=200)
    category: Literal["SPAM", "HARASSMENT", "SAFETY", "MISREPRESENTATION", "OTHER"]
    details: str = Field(min_length=1, max_length=1_000)


class UpdateAccountSettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=60)
    default_autonomy_mode: Literal["AGENT", "COPILOT", "HUMAN"]
    public_sharing_policy: str = Field(min_length=1, max_length=500)
    agent_sharing_policy: str = Field(min_length=1, max_length=500)
    notification_preference: Literal["IN_APP", "IN_APP_AND_EMAIL", "NONE"] | None = None


class DeleteAccountInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation: Literal["DELETE MY PAIRPILOT ACCOUNT"]
