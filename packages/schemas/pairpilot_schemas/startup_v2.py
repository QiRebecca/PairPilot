"""Startup V2 lifecycle contracts and server-side transition rules.

The values in this module are the canonical product vocabulary.  Legacy values
are mapped explicitly so migrations can preserve history instead of silently
guessing what an old record meant.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pairpilot_schemas.domain import IntentStatus as IntentPostState
from pairpilot_schemas.v1 import MemoryStatus as MemoryState


class CoordinationRoomState(StrEnum):
    INTRODUCTION = "INTRODUCTION"
    AGENT_NEGOTIATION = "AGENT_NEGOTIATION"
    NEEDS_HUMAN_INPUT = "NEEDS_HUMAN_INPUT"
    PROPOSAL_READY = "PROPOSAL_READY"
    SHARED = "SHARED"
    ARCHIVED = "ARCHIVED"
    CLOSED = "CLOSED"


class MatchState(StrEnum):
    PROPOSED = "PROPOSED"
    AWAITING_APPROVALS = "AWAITING_APPROVALS"
    CONFIRMED = "CONFIRMED"
    UPCOMING = "UPCOMING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    DISPUTED = "DISPUTED"


class ConnectionState(StrEnum):
    DISCOVERED = "DISCOVERED"
    INTRODUCED = "INTRODUCED"
    COORDINATED = "COORDINATED"
    ESTABLISHED = "ESTABLISHED"
    MUTED = "MUTED"
    BLOCKED = "BLOCKED"


class AutonomyAction(StrEnum):
    DRAFT_POST = "DRAFT_POST"
    PUBLISH_POST = "PUBLISH_POST"
    SEARCH_POSTS = "SEARCH_POSTS"
    CONTACT_PERSONAL_AGENTS = "CONTACT_PERSONAL_AGENTS"
    ASK_COMPATIBILITY_QUESTIONS = "ASK_COMPATIBILITY_QUESTIONS"
    NEGOTIATE_SOFT_PREFERENCES = "NEGOTIATE_SOFT_PREFERENCES"
    PLACE_TEMPORARY_HOLDS = "PLACE_TEMPORARY_HOLDS"
    OPEN_AGENT_ROOMS = "OPEN_AGENT_ROOMS"
    DRAFT_SHARED_MESSAGES = "DRAFT_SHARED_MESSAGES"
    SEND_SHARED_MESSAGES = "SEND_SHARED_MESSAGES"
    SHARE_PROTECTED_INFORMATION = "SHARE_PROTECTED_INFORMATION"
    APPROVE_FINAL_COMMITMENT = "APPROVE_FINAL_COMMITMENT"
    # Legacy aliases retained until migration normalizes stored policies.
    EVALUATE_CANDIDATE = "EVALUATE_CANDIDATE"
    CONTACT_AGENT = "CONTACT_AGENT"
    NEGOTIATE_WITHIN_BOUNDS = "NEGOTIATE_WITHIN_BOUNDS"
    SHARE_CONTACT_FIELD = "SHARE_CONTACT_FIELD"
    ACCEPT_PROPOSAL = "ACCEPT_PROPOSAL"
    COMMIT_MATCH = "COMMIT_MATCH"
    USE_CONFIRMED_MEMORY = "USE_CONFIRMED_MEMORY"


class AutonomyLevel(StrEnum):
    NEVER = "NEVER"
    ASK_FIRST = "ASK_FIRST"
    AUTOMATIC = "AUTOMATIC"
    ALLOW = "ALLOW"


class DecisionKind(StrEnum):
    POST_REVIEW = "POST_REVIEW"
    REQUIREMENT_CLARIFICATION = "REQUIREMENT_CLARIFICATION"
    DISCLOSURE_APPROVAL = "DISCLOSURE_APPROVAL"
    PROPOSAL_APPROVAL = "PROPOSAL_APPROVAL"
    MATCH_COMMITMENT = "MATCH_COMMITMENT"
    MEMORY_CONFIRMATION = "MEMORY_CONFIRMATION"
    ROOM_JOIN = "ROOM_JOIN"
    OFFER_REVALIDATION = "OFFER_REVALIDATION"


class NotificationCategory(StrEnum):
    DECISION_REQUIRED = "DECISION_REQUIRED"
    CANDIDATE_CHANGE = "CANDIDATE_CHANGE"
    AGENT_MESSAGE = "AGENT_MESSAGE"
    PROPOSAL_UPDATE = "PROPOSAL_UPDATE"
    MATCH_UPDATE = "MATCH_UPDATE"
    COMMUNITY_UPDATE = "COMMUNITY_UPDATE"
    SYSTEM = "SYSTEM"


class NotificationState(StrEnum):
    UNREAD = "UNREAD"
    READ = "READ"
    ARCHIVED = "ARCHIVED"


class AutonomyPolicy(BaseModel):
    """Per-action authority; irreversible commitments always require a human."""

    model_config = ConfigDict(extra="forbid")

    owner_uid: str = Field(min_length=1, max_length=160)
    action_levels: dict[AutonomyAction, AutonomyLevel] = Field(default_factory=dict)
    schema_version: int = Field(default=4, ge=4)

    @model_validator(mode="after")
    def protect_irreversible_actions(self) -> AutonomyPolicy:
        for action in (
            AutonomyAction.ACCEPT_PROPOSAL,
            AutonomyAction.COMMIT_MATCH,
            AutonomyAction.APPROVE_FINAL_COMMITMENT,
        ):
            if self.action_levels.get(action) in {
                AutonomyLevel.ALLOW,
                AutonomyLevel.AUTOMATIC,
            }:
                raise ValueError(f"{action.value} cannot be fully automated")
        return self

    def level_for(self, action: AutonomyAction) -> AutonomyLevel:
        return self.action_levels.get(action, AutonomyLevel.ASK_FIRST)


class InvalidStateTransition(ValueError):
    """Raised when an authoritative lifecycle transition is not allowed."""


INTENT_POST_TRANSITIONS: dict[IntentPostState, frozenset[IntentPostState]] = {
    IntentPostState.DRAFT: frozenset(
        {IntentPostState.READY_FOR_REVIEW, IntentPostState.CANCELLED}
    ),
    IntentPostState.READY_FOR_REVIEW: frozenset(
        {IntentPostState.DRAFT, IntentPostState.OPEN, IntentPostState.CANCELLED}
    ),
    IntentPostState.OPEN: frozenset(
        {
            IntentPostState.NEGOTIATING,
            IntentPostState.HELD,
            IntentPostState.MATCHED,
            IntentPostState.PAUSED,
            IntentPostState.EXPIRED,
            IntentPostState.CLOSED,
            IntentPostState.CANCELLED,
        }
    ),
    IntentPostState.NEGOTIATING: frozenset(
        {
            IntentPostState.OPEN,
            IntentPostState.HELD,
            IntentPostState.AWAITING_APPROVAL,
            IntentPostState.PAUSED,
            IntentPostState.EXPIRED,
            IntentPostState.CLOSED,
            IntentPostState.CANCELLED,
        }
    ),
    IntentPostState.HELD: frozenset(
        {
            IntentPostState.OPEN,
            IntentPostState.NEGOTIATING,
            IntentPostState.AWAITING_APPROVAL,
            IntentPostState.PAUSED,
            IntentPostState.EXPIRED,
            IntentPostState.CANCELLED,
        }
    ),
    IntentPostState.AWAITING_APPROVAL: frozenset(
        {
            IntentPostState.OPEN,
            IntentPostState.NEGOTIATING,
            IntentPostState.MATCHED,
            IntentPostState.PAUSED,
            IntentPostState.EXPIRED,
            IntentPostState.CANCELLED,
        }
    ),
    IntentPostState.MATCHED: frozenset(
        {IntentPostState.OPEN, IntentPostState.CLOSED, IntentPostState.CANCELLED}
    ),
    IntentPostState.PAUSED: frozenset(
        {
            IntentPostState.OPEN,
            IntentPostState.CLOSED,
            IntentPostState.EXPIRED,
            IntentPostState.CANCELLED,
        }
    ),
    IntentPostState.CLOSED: frozenset(),
    IntentPostState.EXPIRED: frozenset(),
    IntentPostState.CANCELLED: frozenset(),
}


ROOM_TRANSITIONS: dict[CoordinationRoomState, frozenset[CoordinationRoomState]] = {
    CoordinationRoomState.INTRODUCTION: frozenset(
        {
            CoordinationRoomState.AGENT_NEGOTIATION,
            CoordinationRoomState.NEEDS_HUMAN_INPUT,
            CoordinationRoomState.CLOSED,
        }
    ),
    CoordinationRoomState.AGENT_NEGOTIATION: frozenset(
        {
            CoordinationRoomState.NEEDS_HUMAN_INPUT,
            CoordinationRoomState.PROPOSAL_READY,
            CoordinationRoomState.SHARED,
            CoordinationRoomState.ARCHIVED,
            CoordinationRoomState.CLOSED,
        }
    ),
    CoordinationRoomState.NEEDS_HUMAN_INPUT: frozenset(
        {
            CoordinationRoomState.AGENT_NEGOTIATION,
            CoordinationRoomState.PROPOSAL_READY,
            CoordinationRoomState.SHARED,
            CoordinationRoomState.ARCHIVED,
            CoordinationRoomState.CLOSED,
        }
    ),
    CoordinationRoomState.PROPOSAL_READY: frozenset(
        {
            CoordinationRoomState.AGENT_NEGOTIATION,
            CoordinationRoomState.NEEDS_HUMAN_INPUT,
            CoordinationRoomState.SHARED,
            CoordinationRoomState.ARCHIVED,
            CoordinationRoomState.CLOSED,
        }
    ),
    CoordinationRoomState.SHARED: frozenset(
        {
            CoordinationRoomState.NEEDS_HUMAN_INPUT,
            CoordinationRoomState.ARCHIVED,
            CoordinationRoomState.CLOSED,
        }
    ),
    CoordinationRoomState.ARCHIVED: frozenset(
        {CoordinationRoomState.SHARED, CoordinationRoomState.CLOSED}
    ),
    CoordinationRoomState.CLOSED: frozenset(),
}


MATCH_TRANSITIONS: dict[MatchState, frozenset[MatchState]] = {
    MatchState.PROPOSED: frozenset(
        {MatchState.AWAITING_APPROVALS, MatchState.CANCELLED}
    ),
    MatchState.AWAITING_APPROVALS: frozenset(
        {MatchState.CONFIRMED, MatchState.CANCELLED}
    ),
    MatchState.CONFIRMED: frozenset(
        {
            MatchState.UPCOMING,
            MatchState.IN_PROGRESS,
            MatchState.CANCELLED,
            MatchState.DISPUTED,
        }
    ),
    MatchState.UPCOMING: frozenset(
        {
            MatchState.IN_PROGRESS,
            MatchState.COMPLETED,
            MatchState.CANCELLED,
            MatchState.DISPUTED,
        }
    ),
    MatchState.IN_PROGRESS: frozenset(
        {MatchState.COMPLETED, MatchState.CANCELLED, MatchState.DISPUTED}
    ),
    MatchState.DISPUTED: frozenset({MatchState.COMPLETED, MatchState.CANCELLED}),
    MatchState.COMPLETED: frozenset(),
    MatchState.CANCELLED: frozenset(),
}


CONNECTION_TRANSITIONS: dict[ConnectionState, frozenset[ConnectionState]] = {
    ConnectionState.DISCOVERED: frozenset(
        {ConnectionState.INTRODUCED, ConnectionState.MUTED, ConnectionState.BLOCKED}
    ),
    ConnectionState.INTRODUCED: frozenset(
        {
            ConnectionState.COORDINATED,
            ConnectionState.ESTABLISHED,
            ConnectionState.MUTED,
            ConnectionState.BLOCKED,
        }
    ),
    ConnectionState.COORDINATED: frozenset(
        {
            ConnectionState.ESTABLISHED,
            ConnectionState.MUTED,
            ConnectionState.BLOCKED,
        }
    ),
    ConnectionState.ESTABLISHED: frozenset(
        {
            ConnectionState.COORDINATED,
            ConnectionState.MUTED,
            ConnectionState.BLOCKED,
        }
    ),
    ConnectionState.MUTED: frozenset(
        {
            ConnectionState.DISCOVERED,
            ConnectionState.INTRODUCED,
            ConnectionState.COORDINATED,
            ConnectionState.ESTABLISHED,
            ConnectionState.BLOCKED,
        }
    ),
    ConnectionState.BLOCKED: frozenset({ConnectionState.DISCOVERED}),
}


MEMORY_TRANSITIONS: dict[MemoryState, frozenset[MemoryState]] = {
    MemoryState.PROPOSED: frozenset(
        {MemoryState.CONFIRMED, MemoryState.REJECTED, MemoryState.ARCHIVED}
    ),
    MemoryState.CONFIRMED: frozenset({MemoryState.ARCHIVED}),
    MemoryState.REJECTED: frozenset({MemoryState.ARCHIVED}),
    MemoryState.ARCHIVED: frozenset(),
}


def validate_transition[StateT: StrEnum](
    current: StateT,
    target: StateT,
    transitions: dict[StateT, frozenset[StateT]],
) -> StateT:
    """Return the target for a legal transition, including idempotent replays."""

    if current == target:
        return target
    if target not in transitions.get(current, frozenset()):
        raise InvalidStateTransition(f"invalid transition: {current} -> {target}")
    return target


def validate_intent_post_transition(
    current: IntentPostState, target: IntentPostState
) -> IntentPostState:
    return validate_transition(current, target, INTENT_POST_TRANSITIONS)


def validate_room_transition(
    current: CoordinationRoomState, target: CoordinationRoomState
) -> CoordinationRoomState:
    return validate_transition(current, target, ROOM_TRANSITIONS)


def validate_match_transition(current: MatchState, target: MatchState) -> MatchState:
    return validate_transition(current, target, MATCH_TRANSITIONS)


def validate_connection_transition(
    current: ConnectionState, target: ConnectionState
) -> ConnectionState:
    return validate_transition(current, target, CONNECTION_TRANSITIONS)


def validate_memory_transition(
    current: MemoryState, target: MemoryState
) -> MemoryState:
    return validate_transition(current, target, MEMORY_TRANSITIONS)


LEGACY_ROOM_STATE_MAP: dict[str, CoordinationRoomState] = {
    "ACTIVE": CoordinationRoomState.AGENT_NEGOTIATION,
    "WAITING_FOR_PEER": CoordinationRoomState.AGENT_NEGOTIATION,
    "NEEDS_INPUT": CoordinationRoomState.NEEDS_HUMAN_INPUT,
    "COMPLETED": CoordinationRoomState.ARCHIVED,
    "CLOSED": CoordinationRoomState.CLOSED,
}

LEGACY_MATCH_STATE_MAP: dict[str, MatchState] = {
    "PROPOSED": MatchState.PROPOSED,
    "AWAITING_HUMANS": MatchState.AWAITING_APPROVALS,
    "AWAITING_APPROVAL": MatchState.AWAITING_APPROVALS,
    "COMMITTED": MatchState.CONFIRMED,
    "MATCHED": MatchState.CONFIRMED,
    "COMPLETED": MatchState.COMPLETED,
    "CANCELLED": MatchState.CANCELLED,
}

LEGACY_CONNECTION_STATE_MAP: dict[str, ConnectionState] = {
    "DISCOVERED": ConnectionState.DISCOVERED,
    "INTRODUCED": ConnectionState.INTRODUCED,
    "COORDINATED": ConnectionState.COORDINATED,
    "ESTABLISHED": ConnectionState.ESTABLISHED,
    "ACTIVE": ConnectionState.ESTABLISHED,
    "MUTED": ConnectionState.MUTED,
    "BLOCKED": ConnectionState.BLOCKED,
}


def map_legacy_state[StateT: StrEnum](
    value: object,
    state_type: type[StateT],
    aliases: dict[str, StateT] | None = None,
) -> StateT | None:
    """Map a known legacy value and return None for values needing review."""

    normalized = str(value or "").strip().upper()
    if not normalized:
        return None
    if aliases and normalized in aliases:
        return aliases[normalized]
    try:
        return state_type(normalized)
    except ValueError:
        return None
