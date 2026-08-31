"""Two-sided human authority and atomic multi-user match commitment."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from pairpilot_orchestrator.auth.authorization import (
    require_verified_email,
)
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.generic_agent_runtime import (
    _agent_acceptance_id,
    _decision_id,
    _room_participant_id,
    users_blocked,
)
from pairpilot_orchestrator.multi_user_platform import (
    PRODUCTION_NAMESPACE,
    SCHEMA_VERSION,
    MultiUserStore,
    _clean,
    _create_write,
    _update_write,
    stable_id,
)
from pairpilot_orchestrator.v1_foundation import create_notification


class MultiUserCommitError(Exception):
    """A safe, observable authority precondition failure."""


def _timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    raise MultiUserCommitError("authoritative timestamp is missing")


def _human_approval_id(proposal_id: str, version: int, uid: str) -> str:
    return stable_id("human_approval", proposal_id, str(version), uid)


async def approve_multi_user_proposal(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    proposal_id: str,
    proposal_version: int,
    confirmation: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Record one person's approval; commit only after the other person approves."""

    require_verified_email(principal)
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    proposal = await store.get("proposals", proposal_id)
    if proposal is None or proposal.get("namespace") != PRODUCTION_NAMESPACE:
        raise MultiUserCommitError("current proposal was not found")
    if principal.uid not in {
        str(item) for item in proposal.get("participant_uids", [])
    }:
        raise PermissionError("proposal participant required")
    current_version = int(proposal.get("version", 0))
    if proposal_version != current_version:
        raise MultiUserCommitError("approval references an old proposal version")
    if confirmation != f"APPROVE VERSION {current_version}":
        raise MultiUserCommitError("exact current-version approval is required")
    if proposal.get("status") != "AWAITING_HUMANS":
        existing_match = await store.get("matches", proposal_id)
        if existing_match is not None:
            return {
                "status": "MATCH_COMMITTED",
                "match": _clean(existing_match),
            }
        raise MultiUserCommitError("proposal is not awaiting human approval")
    if _timestamp(proposal.get("expires_at")) <= timestamp:
        raise MultiUserCommitError("proposal expired")
    decision_id = _decision_id(proposal_id, current_version, principal.uid)
    decision = await store.get("decisions", decision_id)
    if decision is None or decision.get("owner_uid") != principal.uid:
        raise MultiUserCommitError("your effect contract is missing")
    expected_contract_hash = str(
        dict(proposal.get("effect_contract_hashes", {})).get(principal.uid, "")
    )
    if (
        not expected_contract_hash
        or decision.get("effect_contract_hash") != expected_contract_hash
        or decision.get("disclosure_hash") != proposal.get("disclosure_hash")
    ):
        raise MultiUserCommitError("effect contract changed after presentation")
    approval_id = _human_approval_id(proposal_id, current_version, principal.uid)
    approval = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "approval_id": approval_id,
        "proposal_id": proposal_id,
        "proposal_version": current_version,
        "approving_uid": principal.uid,
        "decision": "APPROVED",
        "effect_contract_hash": expected_contract_hash,
        "disclosure_hash": str(proposal["disclosure_hash"]),
        "approved_at": timestamp,
        "expires_at": proposal["expires_at"],
    }
    created = await store.create("human_approvals", approval_id, approval)
    if not created:
        existing = await store.get("human_approvals", approval_id)
        if existing is None or any(
            existing.get(field) != approval[field]
            for field in (
                "proposal_version",
                "approving_uid",
                "effect_contract_hash",
                "disclosure_hash",
            )
        ):
            raise MultiUserCommitError("conflicting approval replay detected")
    decision_clean = _clean(decision)
    decision_clean.update(status="RESOLVED", resolved_at=timestamp)
    await store.upsert("decisions", decision_id, decision_clean)
    participant_uids = [str(item) for item in proposal.get("participant_uids", [])]
    approvals = await asyncio.gather(
        *(
            store.get(
                "human_approvals",
                _human_approval_id(proposal_id, current_version, uid),
            )
            for uid in participant_uids
        )
    )
    if any(item is None for item in approvals):
        await store.write_event(
            event_type="human_approval.received_waiting_for_peer.v2",
            run_id=str(proposal["pair_session_id"]),
            producer=principal.uid,
            payload={
                "proposalId": proposal_id,
                "proposalVersion": current_version,
                "approvalsReceived": sum(item is not None for item in approvals),
                "approvalsRequired": len(participant_uids),
            },
            idempotency_key=(
                f"v2:{proposal_id}:v{current_version}:human:{principal.uid}"
            ),
        )
        peer_uid = next(uid for uid in participant_uids if uid != principal.uid)
        await create_notification(
            store,
            owner_uid=peer_uid,
            notification_type="PEER_APPROVED_PROPOSAL",
            title="The other person approved your proposal",
            body=(
                "Your independent approval is still required before any match exists."
            ),
            entity_ids=[proposal_id, str(proposal["room_id"])],
            idempotency_key=(
                f"peer-approved:{proposal_id}:v{current_version}:{principal.uid}"
            ),
            now=timestamp,
        )
        return {
            "status": "WAITING_FOR_OTHER_HUMAN",
            "approvalsReceived": sum(item is not None for item in approvals),
            "approvalsRequired": len(participant_uids),
        }
    match = await commit_dual_approved_match(
        store,
        proposal_id=proposal_id,
        now=timestamp,
    )
    return {"status": "MATCH_COMMITTED", "match": match}


async def commit_dual_approved_match(
    store: MultiUserStore,
    *,
    proposal_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Revalidate both Agents, both humans, both posts and commit once."""

    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    existing_match = await store.get("matches", proposal_id)
    if existing_match is not None:
        return _clean(existing_match)
    proposal = await store.get("proposals", proposal_id)
    if proposal is None:
        raise MultiUserCommitError("proposal is missing")
    version = int(proposal.get("version", 0))
    if proposal.get("status") != "AWAITING_HUMANS":
        raise MultiUserCommitError("proposal is not current")
    if _timestamp(proposal.get("expires_at")) <= timestamp:
        raise MultiUserCommitError("proposal expired")
    participant_uids = [str(item) for item in proposal.get("participant_uids", [])]
    participant_agent_ids = [
        str(item) for item in proposal.get("participant_agent_ids", [])
    ]
    if len(participant_uids) != 2 or len(participant_agent_ids) != 2:
        raise MultiUserCommitError("exactly two participants are required")
    if await users_blocked(store, *participant_uids):
        raise MultiUserCommitError("participants are blocked")
    hold_id = stable_id("hold", proposal_id, str(version))
    source_intent_id = str(proposal["source_intent_id"])
    target_intent_id = str(proposal["target_intent_id"])
    source_task_id = str(proposal["source_task_id"])
    target_task_id = str(proposal["target_task_id"])
    room_id = str(proposal["room_id"])
    (
        hold,
        source_post,
        target_post,
        source_task,
        target_task,
        room,
        first_profile,
        second_profile,
    ) = await asyncio.gather(
        store.get("holds", hold_id),
        store.get("intent_posts", source_intent_id),
        store.get("intent_posts", target_intent_id),
        store.get("task_workspaces", source_task_id),
        store.get("task_workspaces", target_task_id),
        store.get("coordination_rooms", room_id),
        store.get("users", participant_uids[0]),
        store.get("users", participant_uids[1]),
    )
    required = {
        "hold": hold,
        "source post": source_post,
        "target post": target_post,
        "source task": source_task,
        "target task": target_task,
        "room": room,
        "first profile": first_profile,
        "second profile": second_profile,
    }
    missing = [name for name, item in required.items() if item is None]
    if missing:
        raise MultiUserCommitError("authoritative match inputs are missing")
    assert hold is not None
    assert source_post is not None
    assert target_post is not None
    assert source_task is not None
    assert target_task is not None
    assert room is not None
    assert first_profile is not None
    assert second_profile is not None
    if (
        hold.get("active") is not True
        or int(hold.get("proposal_version", 0)) != version
        or _timestamp(hold.get("expires_at")) <= timestamp
    ):
        raise MultiUserCommitError("active current hold required")
    for post in (source_post, target_post):
        if (
            post.get("status") != "AWAITING_APPROVAL"
            or int(post.get("capacity_remaining", 0)) < 1
        ):
            raise MultiUserCommitError("both posts must retain capacity")
    for profile in (first_profile, second_profile):
        if (
            profile.get("account_status") != "ACTIVE"
            or profile.get("email_verified") is not True
        ):
            raise MultiUserCommitError("both accounts must remain active and verified")
    agent_acceptances = await asyncio.gather(
        *(
            store.get(
                "proposal_acceptances",
                _agent_acceptance_id(proposal_id, version, agent_id),
            )
            for agent_id in participant_agent_ids
        )
    )
    human_approvals = await asyncio.gather(
        *(
            store.get(
                "human_approvals",
                _human_approval_id(proposal_id, version, uid),
            )
            for uid in participant_uids
        )
    )
    if any(item is None for item in agent_acceptances):
        raise MultiUserCommitError("both Personal Agents must accept current version")
    if any(item is None for item in human_approvals):
        raise MultiUserCommitError("both humans must approve current version")
    expected_hashes = dict(proposal.get("effect_contract_hashes", {}))
    for approval in human_approvals:
        assert approval is not None
        uid = str(approval.get("approving_uid"))
        if (
            int(approval.get("proposal_version", 0)) != version
            or approval.get("decision") != "APPROVED"
            or approval.get("effect_contract_hash") != expected_hashes.get(uid)
            or approval.get("disclosure_hash") != proposal.get("disclosure_hash")
            or _timestamp(approval.get("expires_at")) <= timestamp
        ):
            raise MultiUserCommitError("a human approval is stale or changed")
    for acceptance in agent_acceptances:
        assert acceptance is not None
        if int(acceptance.get("proposal_version", 0)) != version:
            raise MultiUserCommitError("an Agent acceptance is stale")
    match = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "match_id": proposal_id,
        "proposal_id": proposal_id,
        "proposal_version": version,
        "participant_uids": participant_uids,
        "participant_agent_ids": participant_agent_ids,
        "source_intent_id": source_intent_id,
        "target_intent_id": target_intent_id,
        "room_id": room_id,
        "terms": dict(proposal["terms"]),
        "committed_at": timestamp,
    }
    writes = [_create_write(store, "matches", proposal_id, match)]
    proposal_clean = _clean(proposal)
    proposal_clean.update(status="COMMITTED", committed_at=timestamp)
    writes.append(
        _update_write(
            store,
            "proposals",
            proposal_id,
            proposal_clean,
            update_time=str(proposal["_updateTime"]),
        )
    )
    hold_clean = _clean(hold)
    hold_clean.update(
        active=False,
        status="RELEASED",
        release_reason="match_committed",
        released_at=timestamp,
    )
    writes.append(
        _update_write(
            store,
            "holds",
            hold_id,
            hold_clean,
            update_time=str(hold["_updateTime"]),
        )
    )
    for post, peer_intent_id in (
        (source_post, target_intent_id),
        (target_post, source_intent_id),
    ):
        post_clean = _clean(post)
        post_clean.update(
            status="MATCHED",
            capacity_remaining=int(post["capacity_remaining"]) - 1,
            matched_with_intent_id=peer_intent_id,
            matched_at=timestamp,
            closed_to_new_contacts=True,
            updated_at=timestamp,
        )
        writes.append(
            _update_write(
                store,
                "intent_posts",
                str(post["intent_id"]),
                post_clean,
                update_time=str(post["_updateTime"]),
            )
        )
    for task in (source_task, target_task):
        task_clean = _clean(task)
        task_clean.update(
            status="COMPLETED",
            match_id=proposal_id,
            updated_at=timestamp,
        )
        writes.append(
            _update_write(
                store,
                "task_workspaces",
                str(task["task_id"]),
                task_clean,
                update_time=str(task["_updateTime"]),
            )
        )
    room_clean = _clean(room)
    room_clean.update(
        room_type="SHARED_COORDINATION_ROOM",
        status="ACTIVE",
        human_participation_available=True,
        visibility="SHARED_ROOM",
        updated_at=timestamp,
    )
    writes.append(
        _update_write(
            store,
            "coordination_rooms",
            room_id,
            room_clean,
            update_time=str(room["_updateTime"]),
        )
    )
    for uid, agent_id, peer_uid, peer_agent_id in (
        (
            participant_uids[0],
            participant_agent_ids[0],
            participant_uids[1],
            participant_agent_ids[1],
        ),
        (
            participant_uids[1],
            participant_agent_ids[1],
            participant_uids[0],
            participant_agent_ids[0],
        ),
    ):
        participant_id = _room_participant_id(room_id, uid)
        participant = await store.get("room_participants", participant_id)
        if participant is None:
            raise MultiUserCommitError("room membership is missing")
        participant_clean = _clean(participant)
        participant_clean.update(status="ACTIVE", consented_at=timestamp)
        writes.append(
            _update_write(
                store,
                "room_participants",
                participant_id,
                participant_clean,
                update_time=str(participant["_updateTime"]),
            )
        )
        relationship_id = stable_id("relationship", uid, peer_agent_id)
        relationship = {
            "schema_version": SCHEMA_VERSION,
            "namespace": PRODUCTION_NAMESPACE,
            "relationship_id": relationship_id,
            "owner_uid": uid,
            "owner_agent_id": agent_id,
            "peer_agent_id": peer_agent_id,
            "peer_owner_uid_internal": peer_uid,
            "relation_type": "SUCCESSFUL_COORDINATION",
            "match_id": proposal_id,
            "plans_committed": 1,
            "plans_reported": 0,
            "successful_plans": 0,
            "cancellation_history": 0,
            "commitment_inaccuracy_reports": 0,
            "would_coordinate_again_yes": 0,
            "relevant_communities": [str(source_post.get("community_id", ""))],
            "task_type_compatibility": [str(source_post.get("task_type", ""))],
            "introduction_path": "DIRECT_COMMUNITY_POST",
            "last_interaction_at": timestamp,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        existing_relationship = await store.get("relationships", relationship_id)
        if existing_relationship is None:
            writes.append(
                _create_write(store, "relationships", relationship_id, relationship)
            )
        else:
            relationship.update(
                plans_committed=(
                    int(existing_relationship.get("plans_committed", 0)) + 1
                ),
                plans_reported=int(existing_relationship.get("plans_reported", 0)),
                successful_plans=int(existing_relationship.get("successful_plans", 0)),
                cancellation_history=int(
                    existing_relationship.get("cancellation_history", 0)
                ),
                commitment_inaccuracy_reports=int(
                    existing_relationship.get("commitment_inaccuracy_reports", 0)
                ),
                would_coordinate_again_yes=int(
                    existing_relationship.get("would_coordinate_again_yes", 0)
                ),
                created_at=existing_relationship.get("created_at", timestamp),
            )
            writes.append(
                _update_write(
                    store,
                    "relationships",
                    relationship_id,
                    relationship,
                    update_time=str(existing_relationship["_updateTime"]),
                )
            )
        relationship_event_id = stable_id(
            "relationship_event", proposal_id, uid, "match_committed"
        )
        writes.append(
            _create_write(
                store,
                "relationship_events",
                relationship_event_id,
                {
                    "schema_version": SCHEMA_VERSION,
                    "namespace": PRODUCTION_NAMESPACE,
                    "relationship_event_id": relationship_event_id,
                    "relationship_id": relationship_id,
                    "owner_uid": uid,
                    "match_id": proposal_id,
                    "event_type": "DUAL_APPROVED_MATCH_COMMITTED",
                    "source": "ATOMIC_MATCH_COMMIT",
                    "created_at": timestamp,
                },
            )
        )
        memory_id = stable_id("memory", proposal_id, uid)
        memory = {
            "schema_version": SCHEMA_VERSION,
            "namespace": PRODUCTION_NAMESPACE,
            "memory_id": memory_id,
            "owner_uid": uid,
            "owner_agent_id": agent_id,
            "memory_type": "MATCH_OUTCOME",
            "content": "A human-approved coordination matched successfully.",
            "scope": "MATCH_HISTORY",
            "source": "dual_human_approved_match",
            "confirmation_status": "REVIEWABLE",
            "status": "PROPOSED",
            "match_id": proposal_id,
            "created_at": timestamp,
        }
        writes.append(_create_write(store, "memories", memory_id, memory))
        decision_id = _decision_id(proposal_id, version, uid)
        decision = await store.get("decisions", decision_id)
        if decision is not None:
            decision_clean = _clean(decision)
            decision_clean.update(status="RESOLVED", resolved_at=timestamp)
            writes.append(
                _update_write(
                    store,
                    "decisions",
                    decision_id,
                    decision_clean,
                    update_time=str(decision["_updateTime"]),
                )
            )
    competing_holds = await store.query_documents(
        "holds",
        filters=[("participant_uids", "ARRAY_CONTAINS", participant_uids[0])],
    )
    for competing in competing_holds:
        if competing.get("hold_id") == hold_id or competing.get("active") is not True:
            continue
        competing_clean = _clean(competing)
        competing_clean.update(
            active=False,
            status="RELEASED",
            release_reason="competing_match_committed",
            released_at=timestamp,
        )
        writes.append(
            _update_write(
                store,
                "holds",
                str(competing["hold_id"]),
                competing_clean,
                update_time=str(competing["_updateTime"]),
            )
        )
    try:
        await store.commit_writes(writes)
    except Exception:
        existing_match = await store.get("matches", proposal_id)
        if existing_match is None:
            raise
        return _clean(existing_match)
    await store.write_event(
        event_type="match.committed_after_dual_human_approval.v2",
        run_id=str(proposal["pair_session_id"]),
        producer="commit-authority-v2",
        payload={
            "matchId": proposal_id,
            "proposalVersion": version,
            "participantAgentIds": participant_agent_ids,
            "roomId": room_id,
        },
        idempotency_key=f"v2:{proposal_id}:v{version}:match-committed",
    )
    for uid in participant_uids:
        await create_notification(
            store,
            owner_uid=uid,
            notification_type="MATCH_COMPLETED",
            title="Your match is confirmed",
            body=(
                "Both people approved the same proposal. The shared room is now "
                "open, and contact sharing remains opt-in."
            ),
            entity_ids=[proposal_id, room_id],
            idempotency_key=f"match-completed:{proposal_id}:{uid}",
            now=timestamp,
        )
        await create_notification(
            store,
            owner_uid=uid,
            notification_type="MEMORY_CONFIRMATION_REQUESTED",
            title="Review a new Memory proposal",
            body=(
                "The completed match created a private Memory proposal. It is "
                "inert until you confirm it."
            ),
            entity_ids=[stable_id("memory", proposal_id, uid), proposal_id],
            idempotency_key=f"memory-review:{proposal_id}:{uid}",
            now=timestamp,
        )
    return match
