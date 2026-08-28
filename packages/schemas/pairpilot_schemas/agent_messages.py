"""Validated semantic envelopes for natural-language A2A communication."""

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SpeechAct(StrEnum):
    """Purpose of an agent-to-agent message."""

    INTRODUCTION_REQUEST = "INTRODUCTION_REQUEST"
    INTRODUCTION_RESPONSE = "INTRODUCTION_RESPONSE"
    INFORMATION_REQUEST = "INFORMATION_REQUEST"
    INFORMATION_RESPONSE = "INFORMATION_RESPONSE"
    PROPOSAL = "PROPOSAL"
    COUNTER_PROPOSAL = "COUNTER_PROPOSAL"
    ACCEPTANCE = "ACCEPTANCE"
    REJECTION = "REJECTION"
    WITHDRAWAL = "WITHDRAWAL"


class ClaimSource(StrEnum):
    """Provenance class for a claim; a claim is not authoritative truth."""

    EXPLICIT_USER_INPUT = "explicit_user_input"
    PEER_AGENT_REPORT = "peer_agent_report"
    VERIFIED_WORLD_FACT = "verified_world_fact"
    MODEL_INFERENCE = "model_inference"


class Claim(BaseModel):
    """A typed assertion carried by a peer message."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=80)
    value: object
    source: ClaimSource
    confidence: float = Field(ge=0.0, le=1.0)


class A2AProposal(BaseModel):
    """Proposal data carried for negotiation, never itself a commitment."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    shared_start: date
    shared_end: date
    solo_dates: list[date] = Field(default_factory=list, max_length=14)
    additional_cost_usd: int = Field(ge=0)
    cost_rule: Literal["equal_split_shared_nights"]

    @model_validator(mode="after")
    def dates_must_be_ordered(self) -> "A2AProposal":
        if self.shared_end <= self.shared_start:
            raise ValueError("shared_end must be after shared_start")
        return self


class A2AMessageEnvelope(BaseModel):
    """Natural language plus machine-checkable provenance and routing."""

    model_config = ConfigDict(extra="forbid")

    message_id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    session_id: UUID
    from_agent_id: str = Field(pattern=r"^[a-z0-9-]+$")
    to_agent_id: str = Field(pattern=r"^[a-z0-9-]+$")
    from_intent_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    to_intent_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    pair_session_id: str = Field(pattern=r"^intent-pair-[0-9a-f]{20}$")
    speech_act: SpeechAct
    natural_language: str = Field(min_length=1, max_length=2_000)
    claims: list[Claim] = Field(default_factory=list, max_length=12)
    proposal: A2AProposal | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def expiry_must_be_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
        return value


class PeerClaimDraft(BaseModel):
    """Model-authored peer claim before executor-assigned provenance."""

    model_config = ConfigDict(extra="forbid")

    field: Literal[
        "introduction_decision",
        "introduced_agent_id",
        "introduced_intent_id",
        "availability_start",
        "availability_end",
        "overnight_routine",
        "gender",
        "conference",
        "verified_attendance",
        "budget_compatibility",
        "proposal_version",
    ]
    value: str = Field(min_length=1, max_length=240)
    confidence: float = Field(ge=0.0, le=1.0)


class PeerDecision(BaseModel):
    """Structured output generated independently by one peer ADK agent."""

    model_config = ConfigDict(extra="forbid")

    action: Literal[
        "OFFER_INTRODUCTION",
        "DECLINE_INTRODUCTION",
        "PROVIDE_INFORMATION",
        "ACCEPT_PROPOSAL",
        "COUNTER_PROPOSAL",
        "REJECT_PROPOSAL",
    ]
    speech_act: Literal[
        SpeechAct.INTRODUCTION_RESPONSE,
        SpeechAct.INFORMATION_RESPONSE,
        SpeechAct.ACCEPTANCE,
        SpeechAct.COUNTER_PROPOSAL,
        SpeechAct.REJECTION,
    ]
    natural_language: str = Field(min_length=1, max_length=800)
    claims: list[PeerClaimDraft] = Field(default_factory=list, max_length=10)
    reason: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)
    accepted_proposal_version: int | None = Field(default=None, ge=1)
    introduced_agent_id: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$")
    introduced_intent_id: str | None = Field(default=None, pattern=r"^[a-z0-9_-]+$")

    @model_validator(mode="after")
    def acceptance_requires_version(self) -> "PeerDecision":
        if self.action == "ACCEPT_PROPOSAL" and self.accepted_proposal_version is None:
            raise ValueError("an accepted proposal must reference its version")
        if self.action == "OFFER_INTRODUCTION" and self.introduced_agent_id is None:
            raise ValueError("an offered introduction must name the introduced agent")
        if self.action == "OFFER_INTRODUCTION" and self.introduced_intent_id is None:
            raise ValueError("an offered introduction must name the active intent")
        if self.action == "DECLINE_INTRODUCTION" and (
            self.introduced_agent_id is not None
            or self.introduced_intent_id is not None
        ):
            raise ValueError("a declined introduction cannot name a contact or intent")
        return self
