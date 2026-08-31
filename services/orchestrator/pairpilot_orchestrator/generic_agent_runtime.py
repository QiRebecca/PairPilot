"""Generic user-owned Personal Agent loading and bounded intent negotiation."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import uuid4

from pairpilot_orchestrator.execution_leases import (
    acquire_execution_lease,
    release_execution_lease,
)
from pairpilot_orchestrator.multi_user_platform import (
    MAX_NEW_CONTACTS_PER_TASK,
    PRODUCTION_NAMESPACE,
    SCHEMA_VERSION,
    MultiUserStore,
    _clean,
    _create_write,
    _update_write,
    effect_contract_hash,
    stable_id,
)


class AgentRuntimeError(Exception):
    """The generic Agent cannot safely process the requested bounded turn."""


async def consume_daily_agent_turns(
    store: MultiUserStore,
    owner_uids: list[str],
    *,
    now: datetime | None = None,
) -> None:
    """Atomically charge one bounded model turn to every participating owner."""

    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    quota_date = timestamp.date().isoformat()
    unique_uids = sorted(set(owner_uids))
    for attempt in range(3):
        quotas = await asyncio.gather(
            *(store.get("usage_quotas", uid) for uid in unique_uids)
        )
        writes: list[dict[str, Any]] = []
        for uid, quota in zip(unique_uids, quotas, strict=True):
            if quota is None:
                raise AgentRuntimeError("owner Agent quota is unavailable")
            clean = _clean(quota)
            turns = (
                int(clean.get("agent_turns_today", 0))
                if clean.get("quota_date") == quota_date
                else 0
            )
            limit = int(clean.get("daily_agent_turn_limit", 40))
            if turns >= limit:
                raise AgentRuntimeError("daily Agent turn quota is exhausted")
            clean.update(
                agent_turns_today=turns + 1,
                quota_date=quota_date,
                updated_at=timestamp,
            )
            writes.append(
                _update_write(
                    store,
                    "usage_quotas",
                    uid,
                    clean,
                    update_time=str(quota["_updateTime"]),
                )
            )
        try:
            await store.commit_writes(writes)
            return
        except Exception:
            if attempt == 2:
                raise AgentRuntimeError("Agent quota update conflicted") from None


async def load_personal_agent(
    store: MultiUserStore,
    agent_id: str,
) -> dict[str, Any]:
    """Load any active user-owned Agent without candidate-specific branches."""

    agent = await store.get("personal_agents", agent_id)
    if agent is None or agent.get("status") != "ACTIVE":
        raise AgentRuntimeError("personal agent is unavailable")
    owner_uid = str(agent.get("owner_uid", ""))
    if not owner_uid:
        raise AgentRuntimeError("personal agent has no authoritative owner")
    profile = await store.get("users", owner_uid)
    privacy = await store.get("user_privacy_configs", owner_uid)
    autonomy = await store.get("user_autonomy_configs", owner_uid)
    if (
        profile is None
        or profile.get("account_status") != "ACTIVE"
        or privacy is None
        or autonomy is None
    ):
        raise AgentRuntimeError("personal agent owner is unavailable")
    memories = await store.query_documents(
        "memories", filters=[("owner_uid", "EQUAL", owner_uid)]
    )
    permitted_memories = [
        _clean(item)
        for item in memories
        if item.get("archived") is not True
        and item.get("scope") not in {"PRIVATE_ONLY", "DO_NOT_USE"}
    ]
    return {
        "agent": _clean(agent),
        "owner": _clean(profile),
        "privacy": _clean(privacy),
        "autonomy": _clean(autonomy),
        "permitted_memories": permitted_memories,
    }


def _date_range(post: dict[str, Any]) -> tuple[date, date]:
    constraints = dict(post.get("public_constraints", {}))
    return (
        date.fromisoformat(str(constraints["date_start"])),
        date.fromisoformat(str(constraints["date_end"])),
    )


def compatible_posts(source: dict[str, Any], target: dict[str, Any]) -> bool:
    if source.get("task_type") != target.get("task_type"):
        return False
    source_constraints = dict(source.get("public_constraints", {}))
    target_constraints = dict(target.get("public_constraints", {}))
    if (
        str(source_constraints.get("event", "")).casefold()
        != str(target_constraints.get("event", "")).casefold()
    ):
        return False
    if (
        str(source_constraints.get("location", "")).casefold()
        != str(target_constraints.get("location", "")).casefold()
    ):
        return False
    source_start, source_end = _date_range(source)
    target_start, target_end = _date_range(target)
    return max(source_start, target_start) <= min(source_end, target_end)


async def users_blocked(
    store: MultiUserStore,
    first_uid: str,
    second_uid: str,
) -> bool:
    first_block = stable_id("block", first_uid, second_uid)
    second_block = stable_id("block", second_uid, first_uid)
    first, second = (
        await store.get("blocks", first_block),
        await store.get("blocks", second_block),
    )
    return first is not None or second is not None


def _proposal_id(source_intent_id: str, target_intent_id: str) -> str:
    pair = sorted((source_intent_id, target_intent_id))
    return stable_id("proposal", *pair)


def _decision_id(proposal_id: str, version: int, owner_uid: str) -> str:
    return stable_id("decision_proposal", proposal_id, str(version), owner_uid)


def _agent_acceptance_id(proposal_id: str, version: int, agent_id: str) -> str:
    return stable_id("agent_acceptance", proposal_id, str(version), agent_id)


def _room_participant_id(room_id: str, uid: str) -> str:
    return stable_id("room_participant", room_id, uid)


def _message_document(
    *,
    message_id: str,
    room_id: str,
    task_id: str,
    from_agent: dict[str, Any],
    to_agent_id: str,
    source_intent_id: str,
    target_intent_id: str,
    content: str,
    now: datetime,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "message_id": message_id,
        "room_id": room_id,
        "task_id": task_id,
        "principal_agent_id": str(from_agent["agent_id"]),
        "principal_owner_uid_internal": str(from_agent["owner_uid"]),
        "acting_for_task_id": task_id,
        "source_intent_id": source_intent_id,
        "target_agent_id": to_agent_id,
        "target_intent_id": target_intent_id,
        "speaker_id": str(from_agent["agent_id"]),
        "speaker_type": "PERSONAL_AGENT",
        "authorship": "AGENT_SENT_WITHIN_AUTHORITY",
        "visibility": "AGENTS_ONLY",
        "content": content,
        "provenance": {"runtime": "generic-user-owned-agent-v2"},
        "created_at": now,
    }


async def create_negotiation_for_pair(
    store: MultiUserStore,
    *,
    source_post: dict[str, Any],
    target_post: dict[str, Any],
    agent_messages: dict[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create one idempotent current proposal and two human decisions."""

    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    source_uid = str(source_post["owner_uid"])
    target_uid = str(target_post["owner_uid"])
    if source_uid == target_uid:
        raise AgentRuntimeError("an owner cannot negotiate with their own post")
    if await users_blocked(store, source_uid, target_uid):
        raise AgentRuntimeError("contact is blocked")
    if not compatible_posts(source_post, target_post):
        raise AgentRuntimeError("posts are not compatible")
    source_runtime, target_runtime = await asyncio.gather(
        load_personal_agent(store, str(source_post["owner_agent_id"])),
        load_personal_agent(store, str(target_post["owner_agent_id"])),
    )
    proposal_id = _proposal_id(
        str(source_post["intent_id"]), str(target_post["intent_id"])
    )
    existing = await store.get("proposals", proposal_id)
    if existing is not None:
        return _clean(existing)
    pair_lease = await acquire_execution_lease(
        store,
        resource_id=f"intent-pair:{proposal_id}",
        lease_owner=f"pair-worker-{uuid4().hex}",
    )
    if pair_lease is None:
        existing = await store.get("proposals", proposal_id)
        if existing is not None:
            return _clean(existing)
        raise AgentRuntimeError("intent pair is already being processed")
    version = 1
    source_start, source_end = _date_range(source_post)
    target_start, target_end = _date_range(target_post)
    shared_start = max(source_start, target_start)
    shared_end = min(source_end, target_end)
    terms = {
        "task_type": str(source_post["task_type"]),
        "event": dict(source_post["public_constraints"])["event"],
        "location": dict(source_post["public_constraints"])["location"],
        "shared_start": shared_start.isoformat(),
        "shared_end": shared_end.isoformat(),
        "cost_difference_usd": 0,
        "commitment_scope": "introduction_and_shared_coordination",
    }
    disclosure_hash = sha256(
        json.dumps(terms, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    participant_uids = [source_uid, target_uid]
    participant_agent_ids = [
        str(source_post["owner_agent_id"]),
        str(target_post["owner_agent_id"]),
    ]
    pair_session_id = stable_id(
        "pair", str(source_post["intent_id"]), str(target_post["intent_id"])
    )
    room_id = stable_id("room", pair_session_id)
    hold_id = stable_id("hold", proposal_id, str(version))
    expires_at = timestamp + timedelta(minutes=30)
    contracts: dict[str, dict[str, Any]] = {}
    for viewer_post, peer_post in (
        (source_post, target_post),
        (target_post, source_post),
    ):
        viewer_uid = str(viewer_post["owner_uid"])
        contracts[viewer_uid] = {
            "proposal_id": proposal_id,
            "proposal_version": version,
            "viewer_agent_id": str(viewer_post["owner_agent_id"]),
            "candidate_agent_id": str(peer_post["owner_agent_id"]),
            "candidate_display_name": str(peer_post["public_display_name"]),
            "shared_dates": {
                "start": shared_start.isoformat(),
                "end": shared_end.isoformat(),
            },
            "cost_difference_usd": 0,
            "what_you_disclose": [
                str(viewer_post["public_display_name"]),
                *[str(item) for item in viewer_post.get("public_requirements", [])],
            ],
            "what_you_receive": [
                str(peer_post["public_display_name"]),
                *[str(item) for item in peer_post.get("public_requirements", [])],
            ],
            "remaining_uncertainty": (
                "PairPilot does not verify identity, safety, or compatibility."
            ),
            "hold_expires_at": expires_at,
        }
    contract_hashes = {
        uid: effect_contract_hash(contract) for uid, contract in contracts.items()
    }
    proposal = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "proposal_id": proposal_id,
        "version": version,
        "status": "AWAITING_HUMANS",
        "source_uid": source_uid,
        "target_uid": target_uid,
        "participant_uids": participant_uids,
        "source_agent_id": str(source_post["owner_agent_id"]),
        "target_agent_id": str(target_post["owner_agent_id"]),
        "participant_agent_ids": participant_agent_ids,
        "source_task_id": str(source_post["task_id"]),
        "target_task_id": str(target_post["task_id"]),
        "source_intent_id": str(source_post["intent_id"]),
        "target_intent_id": str(target_post["intent_id"]),
        "pair_session_id": pair_session_id,
        "room_id": room_id,
        "terms": terms,
        "disclosure_hash": disclosure_hash,
        "effect_contract_hashes": contract_hashes,
        "expires_at": expires_at,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    hold = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "hold_id": hold_id,
        "proposal_id": proposal_id,
        "proposal_version": version,
        "participant_uids": participant_uids,
        "source_intent_id": str(source_post["intent_id"]),
        "target_intent_id": str(target_post["intent_id"]),
        "capacity_reserved": 1,
        "active": True,
        "status": "ACTIVE",
        "expires_at": expires_at,
        "created_at": timestamp,
    }
    pair_session = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "pair_session_id": pair_session_id,
        "proposal_id": proposal_id,
        "participant_uids": participant_uids,
        "participant_agent_ids": participant_agent_ids,
        "source_intent_id": str(source_post["intent_id"]),
        "target_intent_id": str(target_post["intent_id"]),
        "status": "HELD",
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    room = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "room_id": room_id,
        "proposal_id": proposal_id,
        "participant_uids": participant_uids,
        "participant_agent_ids": participant_agent_ids,
        "source_task_id": str(source_post["task_id"]),
        "target_task_id": str(target_post["task_id"]),
        "source_intent_id": str(source_post["intent_id"]),
        "target_intent_id": str(target_post["intent_id"]),
        "room_type": "NEGOTIATION_ROOM",
        "status": "NEEDS_INPUT",
        "human_participation_available": False,
        "visibility": "AGENTS_ONLY",
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    writes = [
        _create_write(store, "proposals", proposal_id, proposal),
        _create_write(store, "holds", hold_id, hold),
        _create_write(store, "intent_pair_sessions", pair_session_id, pair_session),
        _create_write(store, "coordination_rooms", room_id, room),
    ]
    for post, runtime in (
        (source_post, source_runtime),
        (target_post, target_runtime),
    ):
        uid = str(post["owner_uid"])
        agent = dict(runtime["agent"])
        task_id = str(post["task_id"])
        decision_id = _decision_id(proposal_id, version, uid)
        contract = contracts[uid]
        decision = {
            "schema_version": SCHEMA_VERSION,
            "namespace": PRODUCTION_NAMESPACE,
            "decision_id": decision_id,
            "owner_uid": uid,
            "task_id": task_id,
            "proposal_id": proposal_id,
            "proposal_version": version,
            "type": "APPROVE_PROPOSAL",
            "status": "OPEN",
            "title": "Your Agent negotiated a current proposal",
            "summary": "Review your exact effect contract independently.",
            "effect_contract": contract,
            "effect_contract_hash": contract_hashes[uid],
            "disclosure_hash": disclosure_hash,
            "expires_at": expires_at,
            "created_at": timestamp,
        }
        acceptance_id = _agent_acceptance_id(
            proposal_id, version, str(agent["agent_id"])
        )
        acceptance = {
            "schema_version": SCHEMA_VERSION,
            "namespace": PRODUCTION_NAMESPACE,
            "acceptance_id": acceptance_id,
            "proposal_id": proposal_id,
            "proposal_version": version,
            "agent_id": str(agent["agent_id"]),
            "owner_uid": uid,
            "accepted_at": timestamp,
            "authority_source": "stored_task_boundaries",
        }
        participant_id = _room_participant_id(room_id, uid)
        participant = {
            "schema_version": SCHEMA_VERSION,
            "namespace": PRODUCTION_NAMESPACE,
            "participant_id": participant_id,
            "room_id": room_id,
            "uid": uid,
            "agent_id": str(agent["agent_id"]),
            "role": "OWNER_AND_AGENT",
            "status": "PENDING_CONSENT",
            "created_at": timestamp,
        }
        writes.extend(
            [
                _create_write(store, "decisions", decision_id, decision),
                _create_write(store, "proposal_acceptances", acceptance_id, acceptance),
                _create_write(store, "room_participants", participant_id, participant),
            ]
        )
    source_message_id = stable_id("room_message", proposal_id, "source")
    target_message_id = stable_id("room_message", proposal_id, "target")
    source_agent = dict(source_runtime["agent"])
    target_agent = dict(target_runtime["agent"])
    if not agent_messages or any(
        str(agent["agent_id"]) not in agent_messages
        for agent in (source_agent, target_agent)
    ):
        await release_execution_lease(store, pair_lease)
        raise AgentRuntimeError(
            "fresh Personal Agent messages are required for a negotiation"
        )
    negotiated_messages = agent_messages
    writes.extend(
        [
            _create_write(
                store,
                "room_messages",
                source_message_id,
                _message_document(
                    message_id=source_message_id,
                    room_id=room_id,
                    task_id=str(source_post["task_id"]),
                    from_agent=source_agent,
                    to_agent_id=str(target_agent["agent_id"]),
                    source_intent_id=str(source_post["intent_id"]),
                    target_intent_id=str(target_post["intent_id"]),
                    content=negotiated_messages[str(source_agent["agent_id"])],
                    now=timestamp,
                ),
            ),
            _create_write(
                store,
                "room_messages",
                target_message_id,
                _message_document(
                    message_id=target_message_id,
                    room_id=room_id,
                    task_id=str(target_post["task_id"]),
                    from_agent=target_agent,
                    to_agent_id=str(source_agent["agent_id"]),
                    source_intent_id=str(target_post["intent_id"]),
                    target_intent_id=str(source_post["intent_id"]),
                    content=negotiated_messages[str(target_agent["agent_id"])],
                    now=timestamp,
                ),
            ),
        ]
    )
    for post in (source_post, target_post):
        clean_post = _clean(post)
        clean_post.update(
            status="AWAITING_APPROVAL",
            active_proposal_id=proposal_id,
            updated_at=timestamp,
        )
        writes.append(
            _update_write(
                store,
                "intent_posts",
                str(post["intent_id"]),
                clean_post,
                update_time=str(post["_updateTime"]),
            )
        )
        task = await store.get("task_workspaces", str(post["task_id"]))
        if task is None:
            raise AgentRuntimeError("proposal task is missing")
        if int(task.get("contact_count", 0)) >= MAX_NEW_CONTACTS_PER_TASK:
            raise AgentRuntimeError("task contact quota is exhausted")
        clean_task = _clean(task)
        clean_task.update(
            status="NEEDS_DECISION",
            active_proposal_id=proposal_id,
            contact_count=int(clean_task.get("contact_count", 0)) + 1,
            updated_at=timestamp,
        )
        decision_id = _decision_id(proposal_id, version, str(post["owner_uid"]))
        decision_ids = list(clean_task.get("decision_ids", []))
        if decision_id not in decision_ids:
            decision_ids.append(decision_id)
        clean_task["decision_ids"] = decision_ids
        writes.append(
            _update_write(
                store,
                "task_workspaces",
                str(post["task_id"]),
                clean_task,
                update_time=str(task["_updateTime"]),
            )
        )
    await store.commit_writes(writes)
    await store.write_event(
        event_type="proposal.awaiting_dual_human_approval.v2",
        run_id=pair_session_id,
        producer="generic-personal-agent-runtime",
        payload={
            "proposalId": proposal_id,
            "proposalVersion": version,
            "participantAgentIds": participant_agent_ids,
        },
        idempotency_key=f"v2:{proposal_id}:v{version}:dual-approval",
    )
    await release_execution_lease(store, pair_lease)
    return proposal


async def _process_published_intent_without_lease(
    store: MultiUserStore,
    intent_id: str,
    agent_messages: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Process one bounded idempotent discovery turn for an active real post."""

    source = await store.get("intent_posts", intent_id)
    if (
        source is None
        or source.get("namespace") != PRODUCTION_NAMESPACE
        or source.get("status") != "OPEN"
    ):
        raise AgentRuntimeError("source post is not discoverable")
    task = await store.get("task_workspaces", str(source["task_id"]))
    if task is None:
        raise AgentRuntimeError("source task is missing")
    if int(task.get("contact_count", 0)) >= MAX_NEW_CONTACTS_PER_TASK:
        raise AgentRuntimeError("task contact quota is exhausted")
    candidates = await store.query_documents(
        "intent_posts", filters=[("status", "EQUAL", "OPEN")]
    )
    compatible = [
        item
        for item in candidates
        if item.get("intent_id") != intent_id
        and item.get("namespace") == PRODUCTION_NAMESPACE
        and item.get("owner_uid") != source.get("owner_uid")
        and compatible_posts(source, item)
    ]
    for target in compatible[:2]:
        if await users_blocked(
            store, str(source["owner_uid"]), str(target["owner_uid"])
        ):
            continue
        return await create_negotiation_for_pair(
            store,
            source_post=source,
            target_post=target,
            agent_messages=agent_messages,
        )
    clean_task = _clean(task)
    clean_task.update(status="SEARCHING", updated_at=datetime.now(UTC))
    await store.upsert("task_workspaces", str(task["task_id"]), clean_task)
    return {"status": "NO_COMPATIBLE_POST_YET", "intent_id": intent_id}


async def process_published_intent(
    store: MultiUserStore,
    intent_id: str,
    agent_messages: dict[str, str] | None = None,
) -> dict[str, Any]:
    source = await store.get("intent_posts", intent_id)
    if source is None:
        raise AgentRuntimeError("source post is not discoverable")
    task_id = str(source.get("task_id", ""))
    if not task_id:
        raise AgentRuntimeError("source task is missing")
    lease = await acquire_execution_lease(
        store,
        resource_id=f"task:{task_id}",
        lease_owner=f"task-worker-{uuid4().hex}",
    )
    if lease is None:
        return {"status": "LEASE_BUSY", "intent_id": intent_id}
    try:
        return await _process_published_intent_without_lease(
            store, intent_id, agent_messages
        )
    finally:
        await release_execution_lease(store, lease)
