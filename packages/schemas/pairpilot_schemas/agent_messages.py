"""Validated semantic envelopes for natural-language A2A communication."""

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class A2AMessageEnvelope(BaseModel):
    """Natural language plus machine-checkable provenance and routing."""

    model_config = ConfigDict(extra="forbid")

    message_id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    session_id: UUID
    from_agent_id: str = Field(pattern=r"^[a-z0-9-]+$")
    to_agent_id: str = Field(pattern=r"^[a-z0-9-]+$")
    speech_act: SpeechAct
    natural_language: str = Field(min_length=1, max_length=2_000)
    claims: list[Claim] = Field(default_factory=list, max_length=12)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def expiry_must_be_timezone_aware(
        cls, value: datetime | None
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
        return value

