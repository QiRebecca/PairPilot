"""Authoritative coordination contracts kept separate from model beliefs."""

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class EvidenceKind(StrEnum):
    VERIFIED_FACT = "VERIFIED_FACT"
    REPORTED_CLAIM = "REPORTED_CLAIM"
    MODEL_INFERENCE = "MODEL_INFERENCE"


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID = Field(default_factory=uuid4)
    subject_agent_id: str
    field: str
    value: object
    kind: EvidenceKind
    source_message_id: str | None = None
    confidence: float = Field(ge=0, le=1)


class Availability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_agent_id: str
    start: date
    end: date
    active: bool = True
    version: int = Field(ge=1)

    def covers(self, start: date, end: date) -> bool:
        return self.active and self.start <= start and self.end >= end


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: UUID = Field(default_factory=uuid4)
    goal_id: UUID
    candidate_agent_id: str
    version: int = Field(ge=1)
    shared_start: date
    shared_end: date
    solo_dates: list[date]
    additional_cost_usd: int = Field(ge=0)
    delegated_maximum_usd: int = Field(ge=0)
    terms: list[str] = Field(min_length=1)
    disclosure_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    expires_at: datetime


class Hold(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hold_id: UUID = Field(default_factory=uuid4)
    proposal_id: UUID
    proposal_version: int
    goal_id: UUID
    candidate_agent_id: str
    expires_at: datetime
    active: bool = True


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_id: UUID = Field(default_factory=uuid4)
    proposal_id: UUID
    proposal_version: int
    disclosure_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Match(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match_id: UUID = Field(default_factory=uuid4)
    proposal_id: UUID
    proposal_version: int
    committed_at: datetime
    provenance_event_ids: list[UUID] = Field(min_length=1)


class RelationshipUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_agent_id: str
    target_agent_id: str
    context: str
    relation_type: str
    successful_plans_delta: int = 0
    successful_introductions_delta: int = 0
    provenance_event_ids: list[UUID] = Field(min_length=1)


class MemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: UUID = Field(default_factory=uuid4)
    owner_agent_id: str
    memory_type: str
    content: str
    scope: str
    source: str
    confidence: float = Field(ge=0, le=1)
    sensitivity: str
    confirmation_status: str
    provenance_event_ids: list[UUID] = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_confirmed_at: datetime | None = None
    decay_policy: str
