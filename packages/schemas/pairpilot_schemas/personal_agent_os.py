"""Typed contracts for PairPilot's persistent Personal Agent product layer."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaskStatus(StrEnum):
    NEEDS_DECISION = "NEEDS_DECISION"
    ACTIVE_NEGOTIATION = "ACTIVE_NEGOTIATION"
    SEARCHING = "SEARCHING"
    DRAFT = "DRAFT"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ConversationKind(StrEnum):
    GLOBAL_PERSONAL_AGENT = "GLOBAL_PERSONAL_AGENT"
    TASK_USER_AGENT = "TASK_USER_AGENT"
    AGENT_NEGOTIATION = "AGENT_NEGOTIATION"
    SHARED_COORDINATION = "SHARED_COORDINATION"


class ConversationRole(StrEnum):
    USER = "USER"
    PERSONAL_AGENT = "PERSONAL_AGENT"
    SYSTEM = "SYSTEM"


class PersonalAgentIntent(StrEnum):
    NEW_TASK = "NEW_TASK"
    EXISTING_TASK_UPDATE = "EXISTING_TASK_UPDATE"
    TASK_STATUS_QUERY = "TASK_STATUS_QUERY"
    CROSS_TASK_QUERY = "CROSS_TASK_QUERY"
    MEMORY_PROPOSAL = "MEMORY_PROPOSAL"
    NETWORK_QUERY = "NETWORK_QUERY"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"


class PresentationAction(StrEnum):
    OPEN_TASK = "OPEN_TASK"
    SHOW_TASK_STATUS = "SHOW_TASK_STATUS"
    SHOW_POST = "SHOW_POST"
    SHOW_RELATED_POSTS = "SHOW_RELATED_POSTS"
    SHOW_CANDIDATE_COMPARISON = "SHOW_CANDIDATE_COMPARISON"
    OPEN_COORDINATION_ROOM = "OPEN_COORDINATION_ROOM"
    SHOW_PROPOSAL = "SHOW_PROPOSAL"
    SHOW_APPROVAL = "SHOW_APPROVAL"
    SHOW_NETWORK_PATH = "SHOW_NETWORK_PATH"
    SHOW_RELATIONSHIP = "SHOW_RELATIONSHIP"
    SHOW_MEMORY = "SHOW_MEMORY"
    FILTER_EXPLORE = "FILTER_EXPLORE"
    CREATE_POST_DRAFT = "CREATE_POST_DRAFT"


class PresentationMode(StrEnum):
    INLINE_CARD = "INLINE_CARD"
    SIDE_PANEL = "SIDE_PANEL"
    NAVIGATE = "NAVIGATE"


class DecisionType(StrEnum):
    REVIEW_POST_DRAFT = "REVIEW_POST_DRAFT"
    APPROVE_PROPOSAL = "APPROVE_PROPOSAL"
    CLARIFY_CONSTRAINT = "CLARIFY_CONSTRAINT"
    APPROVE_DISCLOSURE = "APPROVE_DISCLOSURE"
    REVALIDATE_EXPIRED_OFFER = "REVALIDATE_EXPIRED_OFFER"
    CONFIRM_MEMORY = "CONFIRM_MEMORY"
    JOIN_SHARED_ROOM = "JOIN_SHARED_ROOM"


class DecisionStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"
    EXPIRED = "EXPIRED"


class CandidatePriorityBand(StrEnum):
    RECOMMENDED = "RECOMMENDED"
    PROMISING = "PROMISING"
    NEEDS_INFORMATION = "NEEDS_INFORMATION"
    WAITING = "WAITING"
    NOT_COMPATIBLE = "NOT_COMPATIBLE"
    CLOSED = "CLOSED"
    MATCHED_ELSEWHERE = "MATCHED_ELSEWHERE"


class RoomType(StrEnum):
    INTRODUCTION_ROOM = "INTRODUCTION_ROOM"
    NEGOTIATION_ROOM = "NEGOTIATION_ROOM"
    SHARED_COORDINATION_ROOM = "SHARED_COORDINATION_ROOM"


class RoomStatus(StrEnum):
    ACTIVE = "ACTIVE"
    NEEDS_INPUT = "NEEDS_INPUT"
    WAITING_FOR_PEER = "WAITING_FOR_PEER"
    COMPLETED = "COMPLETED"
    CLOSED = "CLOSED"


class AutonomyMode(StrEnum):
    AGENT = "AGENT"
    COPILOT = "COPILOT"
    HUMAN = "HUMAN"


class SpeakerType(StrEnum):
    HUMAN = "HUMAN"
    PERSONAL_AGENT = "PERSONAL_AGENT"
    INTERNAL_WORKER = "INTERNAL_WORKER"
    COMMUNITY_AGENT = "COMMUNITY_AGENT"
    SYSTEM = "SYSTEM"


class MessageAuthorship(StrEnum):
    HUMAN_WRITTEN = "HUMAN_WRITTEN"
    AGENT_DRAFTED_HUMAN_APPROVED = "AGENT_DRAFTED_HUMAN_APPROVED"
    AGENT_SENT_WITHIN_AUTHORITY = "AGENT_SENT_WITHIN_AUTHORITY"
    SYSTEM_EVENT = "SYSTEM_EVENT"


class MessageVisibility(StrEnum):
    PRIVATE_USER_AGENT = "PRIVATE_USER_AGENT"
    AGENTS_ONLY = "AGENTS_ONLY"
    SHARED_ROOM = "SHARED_ROOM"
    PUBLIC = "PUBLIC"


class TaskWorkspace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(pattern=r"^task_[a-z0-9_-]+$")
    owner_user_id: str = "qi-owner"
    principal_agent_id: str = "qi-agent"
    title: str = Field(min_length=1, max_length=100)
    task_type: str = Field(pattern=r"^[a-z0-9_]+$")
    goal: str = Field(min_length=1, max_length=2_000)
    status: TaskStatus
    conversation_id: str
    intent_id: str
    decision_ids: list[str] = Field(default_factory=list)
    active_proposal_id: str | None = None
    match_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Conversation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    kind: ConversationKind
    principal_agent_id: str = "qi-agent"
    task_id: str | None = None
    participant_ids: list[str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    conversation_id: str
    task_id: str | None = None
    role: ConversationRole
    author_id: str
    content: str = Field(min_length=1, max_length=4_000)
    presentation_directive_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PresentationDirective(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directive_id: str
    action: PresentationAction
    presentation: PresentationMode = PresentationMode.INLINE_CARD
    task_id: str | None = None
    entity_ids: list[str] = Field(default_factory=list, max_length=12)
    explanation: str = Field(min_length=1, max_length=500)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def reject_urls_and_unscoped_navigation(self) -> "PresentationDirective":
        serialized = " ".join([*self.entity_ids, self.explanation]).lower()
        if "http://" in serialized or "https://" in serialized:
            raise ValueError("presentation directives cannot contain URLs")
        if self.presentation == PresentationMode.NAVIGATE and self.action not in {
            PresentationAction.OPEN_TASK,
            PresentationAction.OPEN_COORDINATION_ROOM,
            PresentationAction.FILTER_EXPLORE,
        }:
            raise ValueError("this action cannot navigate")
        return self


class PersonalAgentRoutingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: PersonalAgentIntent
    target_task_id: str | None = None
    clarification_needed: bool
    suggested_title: str | None = Field(default=None, max_length=100)
    task_type: str | None = None
    response_text: str = Field(min_length=1, max_length=800)
    presentation_actions: list[PresentationAction] = Field(
        default_factory=list, max_length=4
    )


class DecisionInboxItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    task_id: str
    type: DecisionType
    status: DecisionStatus = DecisionStatus.OPEN
    title: str = Field(min_length=1, max_length=140)
    summary: str = Field(min_length=1, max_length=600)
    authoritative_entity_ids: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None


class CandidateAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_id: str
    task_id: str
    candidate_intent_id: str
    candidate_agent_id: str
    priority_band: CandidatePriorityBand
    current_status: str
    verified_support: list[str] = Field(default_factory=list)
    peer_reported_support: list[str] = Field(default_factory=list)
    negotiated_support: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    relationship_path: list[str] = Field(default_factory=list)
    active_room_id: str | None = None
    active_proposal_id: str | None = None
    evidence_event_ids: list[str] = Field(default_factory=list)
    last_updated_turn_id: str | None = None
    observable_explanation: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CoordinationRoom(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_id: str
    task_id: str
    source_intent_id: str
    target_intent_id: str
    participant_agent_ids: list[str] = Field(min_length=2)
    room_type: RoomType
    status: RoomStatus
    autonomy_mode: AutonomyMode = AutonomyMode.AGENT
    human_participation_available: bool = False
    latest_meaningful_event: str
    unread_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RoomMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    room_id: str
    task_id: str
    source_intent_id: str
    target_intent_id: str
    speaker_id: str
    speaker_type: SpeakerType
    authorship: MessageAuthorship
    visibility: MessageVisibility
    content: str = Field(min_length=1, max_length=4_000)
    reply_to: str | None = None
    provenance: dict[str, str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def enforce_channel_authorship(self) -> "RoomMessage":
        if (
            self.visibility == MessageVisibility.AGENTS_ONLY
            and self.speaker_type == SpeakerType.HUMAN
        ):
            raise ValueError("humans cannot write directly to agents-only transcripts")
        if (
            self.authorship == MessageAuthorship.HUMAN_WRITTEN
            and self.speaker_type != SpeakerType.HUMAN
        ):
            raise ValueError("human-written messages require a human speaker")
        return self
