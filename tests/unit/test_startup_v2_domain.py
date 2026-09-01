from __future__ import annotations

import pytest
from pairpilot_schemas import (
    AutonomyAction,
    AutonomyLevel,
    AutonomyPolicy,
    ConnectionState,
    CoordinationRoomState,
    IntentPostState,
    InvalidStateTransition,
    MatchState,
    MemoryState,
    validate_connection_transition,
    validate_intent_post_transition,
    validate_match_transition,
    validate_memory_transition,
    validate_room_transition,
)
from pairpilot_schemas.startup_v2 import (
    LEGACY_CONNECTION_STATE_MAP,
    LEGACY_MATCH_STATE_MAP,
    LEGACY_ROOM_STATE_MAP,
    map_legacy_state,
)
from pydantic import ValidationError


@pytest.mark.parametrize(
    ("validator", "current", "target"),
    [
        (validate_intent_post_transition, IntentPostState.DRAFT, IntentPostState.OPEN),
        (
            validate_room_transition,
            CoordinationRoomState.INTRODUCTION,
            CoordinationRoomState.PROPOSAL_READY,
        ),
        (validate_match_transition, MatchState.PROPOSED, MatchState.CONFIRMED),
        (
            validate_connection_transition,
            ConnectionState.DISCOVERED,
            ConnectionState.ESTABLISHED,
        ),
        (validate_memory_transition, MemoryState.ARCHIVED, MemoryState.CONFIRMED),
    ],
)
def test_invalid_lifecycle_transitions_are_rejected(validator, current, target) -> None:
    with pytest.raises(InvalidStateTransition):
        validator(current, target)


def test_legal_and_idempotent_transitions_are_accepted() -> None:
    assert (
        validate_intent_post_transition(
            IntentPostState.READY_FOR_REVIEW, IntentPostState.OPEN
        )
        == IntentPostState.OPEN
    )
    assert (
        validate_room_transition(
            CoordinationRoomState.AGENT_NEGOTIATION,
            CoordinationRoomState.NEEDS_HUMAN_INPUT,
        )
        == CoordinationRoomState.NEEDS_HUMAN_INPUT
    )
    assert (
        validate_match_transition(MatchState.CONFIRMED, MatchState.CONFIRMED)
        == MatchState.CONFIRMED
    )


def test_legacy_state_mapping_is_explicit_and_unknown_values_require_review() -> None:
    assert (
        map_legacy_state("active", CoordinationRoomState, LEGACY_ROOM_STATE_MAP)
        == CoordinationRoomState.AGENT_NEGOTIATION
    )
    assert (
        map_legacy_state("committed", MatchState, LEGACY_MATCH_STATE_MAP)
        == MatchState.CONFIRMED
    )
    assert (
        map_legacy_state("active", ConnectionState, LEGACY_CONNECTION_STATE_MAP)
        == ConnectionState.ESTABLISHED
    )
    assert map_legacy_state("mystery", MatchState, LEGACY_MATCH_STATE_MAP) is None


def test_autonomy_defaults_to_ask_and_blocks_automatic_commitment() -> None:
    policy = AutonomyPolicy(
        owner_uid="user-a",
        action_levels={AutonomyAction.DRAFT_POST: AutonomyLevel.ALLOW},
    )
    assert policy.level_for(AutonomyAction.DRAFT_POST) == AutonomyLevel.ALLOW
    assert policy.level_for(AutonomyAction.CONTACT_AGENT) == AutonomyLevel.ASK_FIRST
    with pytest.raises(ValidationError, match="cannot be fully automated"):
        AutonomyPolicy(
            owner_uid="user-a",
            action_levels={AutonomyAction.COMMIT_MATCH: AutonomyLevel.ALLOW},
        )
