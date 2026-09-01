"""Authoritative coordination contracts kept separate from model beliefs."""

from datetime import UTC, date, datetime
from enum import StrEnum
from hashlib import sha256
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceKind(StrEnum):
    VERIFIED_FACT = "VERIFIED_FACT"
    REPORTED_CLAIM = "REPORTED_CLAIM"
    MODEL_INFERENCE = "MODEL_INFERENCE"


class IntentStatus(StrEnum):
    """Authoritative lifecycle of one user-owned marketplace post."""

    DRAFT = "DRAFT"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    OPEN = "OPEN"
    NEGOTIATING = "NEGOTIATING"
    HELD = "HELD"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    MATCHED = "MATCHED"
    CLOSED = "CLOSED"
    PAUSED = "PAUSED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class FieldSource(StrEnum):
    """Where one extracted intent field came from."""

    EXPLICIT_USER_INPUT = "explicit_user_input"
    EXISTING_CONFIRMED_MEMORY = "existing_confirmed_memory"
    AGENT_INFERENCE = "agent_inference"
    USER_EDIT = "user_edit"


class IntentPublicConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event: str = Field(min_length=1, max_length=80)
    location: str = Field(min_length=1, max_length=120)
    date_start: date
    date_end: date
    roommate_gender_preference: str = Field(min_length=1, max_length=40)

    @property
    def nights(self) -> int:
        return (self.date_end - self.date_start).days


class NegotiationBoundaries(BaseModel):
    model_config = ConfigDict(extra="forbid")

    partial_date_overlap_allowed: bool
    maximum_additional_cost_usd: int = Field(ge=0, le=10_000)


class IntentPost(BaseModel):
    """Public, capacity-bearing need monitored by one personal agent."""

    model_config = ConfigDict(extra="forbid")

    intent_id: str = Field(pattern=r"^[a-z0-9_-]+$")
    owner_agent_id: str = Field(pattern=r"^[a-z0-9-]+$")
    intent_type: str = Field(pattern=r"^[a-z0-9_]+$")
    raw_user_goal_ref: str
    public_title: str = Field(min_length=1, max_length=120)
    public_summary: str = Field(min_length=1, max_length=600)
    public_constraints: IntentPublicConstraints
    public_requirements: list[str] = Field(default_factory=list, max_length=12)
    negotiation_boundaries: NegotiationBoundaries
    capacity: int = Field(ge=0, le=20)
    capacity_remaining: int = Field(ge=0, le=20)
    status: IntentStatus
    version: int = Field(ge=1)
    field_provenance: dict[str, FieldSource]
    created_at: datetime
    published_at: datetime | None = None
    expires_at: datetime
    provenance: dict[str, str]

    @model_validator(mode="after")
    def validate_lifecycle_and_capacity(self) -> "IntentPost":
        if self.public_constraints.date_end <= self.public_constraints.date_start:
            raise ValueError("intent date_end must be after date_start")
        if self.capacity_remaining > self.capacity:
            raise ValueError("capacity_remaining cannot exceed capacity")
        if self.status == IntentStatus.OPEN and self.published_at is None:
            raise ValueError("an OPEN intent must have published_at")
        if self.expires_at.tzinfo is None or self.created_at.tzinfo is None:
            raise ValueError("intent timestamps must be timezone-aware")
        return self


class IntentPrivateContext(BaseModel):
    """Owner-scoped intent data that must never enter the public registry."""

    model_config = ConfigDict(extra="forbid")

    intent_id: str
    owner_agent_id: str
    raw_user_goal: str
    agent_only_constraints: dict[str, object]
    protected_memory_refs: list[str]
    protected_fact_count: int = Field(ge=0)
    readable_by: list[str] = Field(min_length=1)


def canonical_intent_pair(source_intent_id: str, target_intent_id: str) -> str:
    """Return an order-independent, stable negotiation-session identifier."""

    first, second = sorted((source_intent_id, target_intent_id))
    digest = sha256(f"{first}\n{second}".encode()).hexdigest()[:20]
    return f"intent-pair-{digest}"


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
    goal_id: UUID | None = None
    source_intent_id: str | None = None
    target_intent_id: str | None = None
    pair_session_id: str | None = None
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

    @model_validator(mode="after")
    def require_coordination_scope(self) -> "Proposal":
        if self.goal_id is None and not (
            self.source_intent_id and self.target_intent_id and self.pair_session_id
        ):
            raise ValueError("proposal requires legacy goal or intent-pair scope")
        return self


class Hold(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hold_id: UUID = Field(default_factory=uuid4)
    proposal_id: UUID
    proposal_version: int
    goal_id: UUID | None = None
    source_intent_id: str | None = None
    target_intent_id: str | None = None
    pair_session_id: str | None = None
    candidate_agent_id: str
    capacity_reserved: int = Field(default=1, ge=1)
    status: str = "ACTIVE"
    idempotency_key: str | None = None
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
