from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from pairpilot_orchestrator.domain.authority import (
    AuthorityError,
    CoordinationAuthority,
    calculate_additional_cost,
)
from pairpilot_schemas import Availability, Proposal

NOW = datetime.now(UTC)


def proposal(*, goal_id=None, version=1, expires_at=None) -> Proposal:
    return Proposal(
        goal_id=goal_id or uuid4(),
        candidate_agent_id="candidate-agent",
        version=version,
        shared_start=date(2026, 7, 7),
        shared_end=date(2026, 7, 10),
        solo_dates=[date(2026, 7, 6)],
        additional_cost_usd=62,
        delegated_maximum_usd=70,
        terms=["The three shared nights are split equally."],
        disclosure_hash=sha256(b"quiet compatibility").hexdigest(),
        expires_at=expires_at or NOW + timedelta(hours=1),
    )


def ready_authority(item: Proposal) -> CoordinationAuthority:
    authority = CoordinationAuthority()
    authority.add_proposal(item)
    authority.set_availability(
        Availability(
            candidate_agent_id=item.candidate_agent_id,
            start=item.shared_start,
            end=item.shared_end,
            version=1,
        )
    )
    authority.place_hold(item.proposal_id, expires_at=NOW + timedelta(minutes=20))
    authority.accept(item.proposal_id, agent_id="qi-agent")
    authority.accept(item.proposal_id, agent_id=item.candidate_agent_id)
    authority.approve(
        item.proposal_id,
        proposal_version=item.version,
        current_disclosure_hash=item.disclosure_hash,
    )
    return authority


def test_partial_plan_cost_is_exactly_sixty_two_dollars() -> None:
    assert (
        calculate_additional_cost(
            total_nights=4, shared_nights=3, nightly_room_cost_usd=124
        )
        == 62
    )


def test_no_commit_without_human_approval() -> None:
    item = proposal()
    authority = ready_authority(item)
    authority.approvals.clear()
    with pytest.raises(AuthorityError, match="human approval"):
        authority.commit(item.proposal_id, now=NOW)


def test_old_approval_cannot_authorize_new_version() -> None:
    goal_id = uuid4()
    first = proposal(goal_id=goal_id, version=1)
    authority = ready_authority(first)
    next(iter(authority.holds.values())).active = False
    second = proposal(goal_id=goal_id, version=2)
    authority.add_proposal(second)
    authority.place_hold(second.proposal_id, expires_at=NOW + timedelta(minutes=20))
    authority.accept(second.proposal_id, agent_id="qi-agent")
    authority.accept(second.proposal_id, agent_id=second.candidate_agent_id)
    authority.approvals[second.proposal_id] = authority.approvals[
        first.proposal_id
    ].model_copy(update={"proposal_id": second.proposal_id})
    with pytest.raises(AuthorityError, match="old proposal version"):
        authority.commit(second.proposal_id, now=NOW)


def test_expired_hold_cannot_commit() -> None:
    item = proposal()
    authority = ready_authority(item)
    next(iter(authority.holds.values())).expires_at = NOW - timedelta(seconds=1)
    with pytest.raises(AuthorityError, match="active current hold"):
        authority.commit(item.proposal_id, now=NOW)


def test_only_one_conflicting_hold_can_be_active() -> None:
    goal_id = uuid4()
    first = proposal(goal_id=goal_id)
    second = proposal(goal_id=goal_id)
    second.candidate_agent_id = "other-candidate-agent"
    authority = CoordinationAuthority()
    authority.add_proposal(first)
    authority.add_proposal(second)
    authority.place_hold(first.proposal_id, expires_at=NOW + timedelta(minutes=20))
    with pytest.raises(AuthorityError, match="conflicting active hold"):
        authority.place_hold(second.proposal_id, expires_at=NOW + timedelta(minutes=20))


def test_duplicate_commit_returns_same_match_and_one_relationship_update() -> None:
    item = proposal()
    authority = ready_authority(item)
    first = authority.commit(item.proposal_id, now=NOW)
    second = authority.commit(item.proposal_id, now=NOW)
    assert first.match_id == second.match_id
    assert len(authority.relationship_updates) == 1
    assert authority.relationship_updates[0].provenance_event_ids
    assert len(authority.memories) == 1


def test_changed_availability_blocks_commit() -> None:
    item = proposal()
    authority = ready_authority(item)
    authority.set_availability(
        Availability(
            candidate_agent_id=item.candidate_agent_id,
            start=date(2026, 7, 8),
            end=date(2026, 7, 10),
            version=2,
        )
    )
    with pytest.raises(AuthorityError, match="no longer available"):
        authority.commit(item.proposal_id, now=NOW)


def test_changed_disclosure_scope_blocks_commit() -> None:
    item = proposal()
    authority = ready_authority(item)
    authority.approvals[item.proposal_id].disclosure_hash = sha256(
        b"different disclosure"
    ).hexdigest()
    with pytest.raises(AuthorityError, match="disclosure scope changed"):
        authority.commit(item.proposal_id, now=NOW)
