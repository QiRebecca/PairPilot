"""Bounded multi-candidate discovery, evidence, rooms, and dynamic ranking."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from typing import Any

from pairpilot_orchestrator.execution_leases import (
    acquire_execution_lease,
    release_execution_lease,
)
from pairpilot_orchestrator.generic_agent_runtime import (
    AgentRuntimeError,
    compatible_posts,
    consume_daily_agent_turns,
    load_personal_agent,
    users_blocked,
)
from pairpilot_orchestrator.multi_user_agent import negotiate_pair_with_adk
from pairpilot_orchestrator.multi_user_platform import (
    MAX_NEW_CONTACTS_PER_TASK,
    PRODUCTION_NAMESPACE,
    SCHEMA_VERSION,
    MultiUserStore,
    _clean,
    stable_id,
)
from pairpilot_orchestrator.v1_foundation import create_notification

MAX_POSTS_INSPECTED = 20
MAX_SIMULTANEOUS_NEGOTIATIONS = 3
MAX_A2A_ROUNDS_PER_CANDIDATE = 6
ACTIVE_CANDIDATE_STATES = {
    "RECOMMENDED",
    "PROMISING",
    "NEEDS_INFORMATION",
    "WAITING",
    "BACKUP",
}
TERMINAL_CANDIDATE_STATES = {
    "NOT_COMPATIBLE",
    "WITHDRAWN",
    "MATCHED_ELSEWHERE",
    "CLOSED",
}


def _assessment_id(task_id: str, candidate_intent_id: str) -> str:
    return stable_id("candidate", task_id, candidate_intent_id)


def _candidate_room_id(source_intent_id: str, target_intent_id: str) -> str:
    return stable_id("candidate_room", *sorted((source_intent_id, target_intent_id)))


def _overlap_days(source: dict[str, Any], target: dict[str, Any]) -> int:
    source_constraints = dict(source.get("public_constraints", {}))
    target_constraints = dict(target.get("public_constraints", {}))
    source_start = date.fromisoformat(str(source_constraints["date_start"]))
    source_end = date.fromisoformat(str(source_constraints["date_end"]))
    target_start = date.fromisoformat(str(target_constraints["date_start"]))
    target_end = date.fromisoformat(str(target_constraints["date_end"]))
    return max(
        0, (min(source_end, target_end) - max(source_start, target_start)).days + 1
    )


def _evidence_score(assessment: dict[str, Any]) -> int:
    """Order evidence internally while the UI shows reasons, not percentages."""

    state_weight = {
        "RECOMMENDED": 60,
        "PROMISING": 50,
        "NEEDS_INFORMATION": 35,
        "WAITING": 30,
        "BACKUP": 20,
    }.get(str(assessment.get("state")), 0)
    return (
        state_weight
        + int(assessment.get("date_overlap_days", 0)) * 4
        + len(list(assessment.get("negotiated_support", []))) * 3
        + len(list(assessment.get("verified_support", []))) * 2
        - len(list(assessment.get("conflicts", []))) * 12
        - len(list(assessment.get("uncertainties", [])))
    )


async def rerank_task_candidates(
    store: MultiUserStore,
    task_id: str,
    *,
    invocation_id: str,
    reason_category: str,
    evidence_ids: list[str],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    assessments = await store.query_documents(
        "candidate_assessments", filters=[("task_id", "EQUAL", task_id)]
    )
    active = [
        item for item in assessments if item.get("state") in ACTIVE_CANDIDATE_STATES
    ]
    previous_ordering = [
        str(item["candidate_intent_id"])
        for item in sorted(active, key=lambda item: int(item.get("current_rank", 999)))
    ]
    ordered = sorted(
        active,
        key=lambda item: (
            -_evidence_score(item),
            str(item.get("last_material_change_at", "")),
            str(item.get("candidate_intent_id", "")),
        ),
    )
    for rank, assessment in enumerate(ordered, start=1):
        clean = _clean(assessment)
        clean["current_rank"] = rank
        clean["priority_band"] = (
            "PRIMARY" if rank == 1 else "ALTERNATIVE" if rank <= 3 else "BACKUP"
        )
        if rank == 1 and clean.get("state") == "PROMISING":
            clean["state"] = "RECOMMENDED"
        elif rank > 1 and clean.get("state") == "RECOMMENDED":
            clean["state"] = "PROMISING"
        clean["updated_at"] = timestamp
        await store.upsert("candidate_assessments", str(clean["assessment_id"]), clean)
    new_ordering = [str(item["candidate_intent_id"]) for item in ordered]
    if previous_ordering != new_ordering or evidence_ids:
        rank_event_id = stable_id(
            "rank_event",
            task_id,
            invocation_id,
            reason_category,
            "|".join(evidence_ids),
        )
        await store.create(
            "candidate_rank_events",
            rank_event_id,
            {
                "schema_version": SCHEMA_VERSION,
                "namespace": PRODUCTION_NAMESPACE,
                "rank_event_id": rank_event_id,
                "task_id": task_id,
                "owner_uid": str(ordered[0].get("owner_uid", "")) if ordered else "",
                "previous_ordering": previous_ordering,
                "new_ordering": new_ordering,
                "evidence_ids": evidence_ids,
                "agent_invocation_id": invocation_id,
                "reason_category": reason_category,
                "created_at": timestamp,
            },
        )
    return [
        _clean(
            await store.get("candidate_assessments", str(item["assessment_id"])) or item
        )
        for item in ordered
    ]


async def record_candidate_exchange(
    store: MultiUserStore,
    *,
    source_post: dict[str, Any],
    target_post: dict[str, Any],
    agent_messages: dict[str, str],
    invocation_id: str,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Persist one pair's scoped evidence without creating a commitment proposal."""

    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    source_intent_id = str(source_post["intent_id"])
    target_intent_id = str(target_post["intent_id"])
    room_id = _candidate_room_id(source_intent_id, target_intent_id)
    source_agent_id = str(source_post["owner_agent_id"])
    target_agent_id = str(target_post["owner_agent_id"])
    participant_uids = [str(source_post["owner_uid"]), str(target_post["owner_uid"])]
    participant_agent_ids = [source_agent_id, target_agent_id]
    await store.create(
        "coordination_rooms",
        room_id,
        {
            "schema_version": SCHEMA_VERSION,
            "namespace": PRODUCTION_NAMESPACE,
            "room_id": room_id,
            "room_type": "INTRODUCTION_ROOM",
            "source_task_id": str(source_post["task_id"]),
            "target_task_id": str(target_post["task_id"]),
            "source_intent_id": source_intent_id,
            "target_intent_id": target_intent_id,
            "participant_uids": participant_uids,
            "participant_agent_ids": participant_agent_ids,
            "autonomy_mode": "COPILOT",
            "status": "ACTIVE",
            "human_participation_available": False,
            "visibility": "AGENTS_ONLY",
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    evidence_ids: list[str] = []
    for post, peer, agent_id, peer_agent_id in (
        (source_post, target_post, source_agent_id, target_agent_id),
        (target_post, source_post, target_agent_id, source_agent_id),
    ):
        message_id = stable_id("candidate_message", room_id, agent_id, invocation_id)
        evidence_ids.append(message_id)
        await store.create(
            "room_messages",
            message_id,
            {
                "schema_version": SCHEMA_VERSION,
                "namespace": PRODUCTION_NAMESPACE,
                "message_id": message_id,
                "room_id": room_id,
                "task_id": str(post["task_id"]),
                "principal_agent_id": agent_id,
                "principal_owner_uid_internal": str(post["owner_uid"]),
                "acting_for_task_id": str(post["task_id"]),
                "source_intent_id": str(post["intent_id"]),
                "target_agent_id": peer_agent_id,
                "target_intent_id": str(peer["intent_id"]),
                "speaker_id": agent_id,
                "speaker_type": "PERSONAL_AGENT",
                "authorship": "AGENT_SENT_WITHIN_AUTHORITY",
                "visibility": "AGENTS_ONLY",
                "content": agent_messages[agent_id],
                "provenance": {
                    "runtime": "candidate-pool-v1",
                    "invocation_id": invocation_id,
                },
                "created_at": timestamp,
            },
        )
    updated: list[dict[str, Any]] = []
    for own_post, candidate_post in (
        (source_post, target_post),
        (target_post, source_post),
    ):
        task_id = str(own_post["task_id"])
        candidate_intent_id = str(candidate_post["intent_id"])
        assessment_id = _assessment_id(task_id, candidate_intent_id)
        existing = await store.get("candidate_assessments", assessment_id)
        assessment = _clean(existing or {})
        assessment.update(
            schema_version=SCHEMA_VERSION,
            namespace=PRODUCTION_NAMESPACE,
            assessment_id=assessment_id,
            owner_uid=str(own_post["owner_uid"]),
            task_id=task_id,
            source_intent_id=str(own_post["intent_id"]),
            candidate_intent_id=candidate_intent_id,
            candidate_agent_id=str(candidate_post["owner_agent_id"]),
            candidate_display_name=str(
                candidate_post.get("public_display_name", "Community member")
            ),
            state="PROMISING",
            priority_band="ALTERNATIVE",
            current_rank=int(assessment.get("current_rank", 999)),
            verified_support=[
                {"fact": "Same active community", "evidence_id": candidate_intent_id},
                {
                    "fact": "Compatible intent type and location",
                    "evidence_id": candidate_intent_id,
                },
                {
                    "fact": (
                        f"{_overlap_days(own_post, candidate_post)} overlapping day(s)"
                    ),
                    "evidence_id": candidate_intent_id,
                },
            ],
            peer_reported_support=[
                {
                    "claim": str(candidate_post.get("public_summary", "")),
                    "evidence_id": candidate_intent_id,
                }
            ],
            negotiated_support=[
                {
                    "claim": agent_messages[str(candidate_post["owner_agent_id"])],
                    "evidence_id": evidence_ids[1 if own_post is source_post else 0],
                }
            ],
            conflicts=[],
            uncertainties=[
                "Identity, safety, and compatibility are not verified by PairPilot."
            ],
            relationship_path="DIRECT_COMMUNITY_POST",
            room_id=room_id,
            proposal_id=assessment.get("proposal_id"),
            evidence_event_ids=sorted(
                set(list(assessment.get("evidence_event_ids", [])) + evidence_ids)
            ),
            date_overlap_days=_overlap_days(own_post, candidate_post),
            a2a_round_count=int(assessment.get("a2a_round_count", 0)) + 1,
            last_material_change_at=timestamp,
            updated_at=timestamp,
        )
        if existing is None:
            assessment["created_at"] = timestamp
        await store.upsert("candidate_assessments", assessment_id, assessment)
        await rerank_task_candidates(
            store,
            task_id,
            invocation_id=invocation_id,
            reason_category="NEW_AGENT_EVIDENCE",
            evidence_ids=evidence_ids,
            now=timestamp,
        )
        await create_notification(
            store,
            owner_uid=str(own_post["owner_uid"]),
            notification_type="CANDIDATE_FOUND",
            title="Your Agent found a promising candidate",
            body=(
                f"{assessment['candidate_display_name']} is now in the ranked "
                "candidate pool."
            ),
            entity_ids=[task_id, candidate_intent_id, room_id],
            idempotency_key=f"candidate:{task_id}:{candidate_intent_id}",
            now=timestamp,
        )
        updated.append(assessment)
    for post in (source_post, target_post):
        task = await store.get("task_workspaces", str(post["task_id"]))
        if task is not None:
            clean_task = _clean(task)
            existing_candidate_ids = set(clean_task.get("candidate_intent_ids", []))
            peer_id = target_intent_id if post is source_post else source_intent_id
            was_new = peer_id not in existing_candidate_ids
            existing_candidate_ids.add(peer_id)
            clean_task.update(
                status="NEGOTIATING",
                candidate_intent_ids=sorted(existing_candidate_ids),
                contact_count=int(clean_task.get("contact_count", 0))
                + (1 if was_new else 0),
                updated_at=timestamp,
            )
            await store.upsert("task_workspaces", str(post["task_id"]), clean_task)
    await store.write_event(
        event_type="candidate.updated.v1",
        run_id=str(source_post["task_id"]),
        producer="candidate-pool-v1",
        payload={
            "sourceIntentId": source_intent_id,
            "targetIntentId": target_intent_id,
            "roomId": room_id,
        },
        idempotency_key=f"candidate:{source_intent_id}:{target_intent_id}:{invocation_id}",
    )
    return updated


async def process_candidate_pool_event(
    store: MultiUserStore,
    intent_id: str,
    *,
    requested_target_id: str | None = None,
) -> dict[str, Any]:
    """Inspect 20 posts and contact three new candidates per bounded turn."""

    source = await store.get("intent_posts", intent_id)
    if (
        source is None
        or source.get("status") != "OPEN"
        or source.get("namespace") != PRODUCTION_NAMESPACE
    ):
        raise AgentRuntimeError("source post is not discoverable")
    task_id = str(source["task_id"])
    lease = await acquire_execution_lease(
        store,
        resource_id=f"candidate-pool:{task_id}",
        lease_owner=(
            "candidate-pool-"
            + stable_id("turn", intent_id, datetime.now(UTC).isoformat())
        ),
    )
    if lease is None:
        return {"status": "LEASE_BUSY", "intent_id": intent_id}
    try:
        task = await store.get("task_workspaces", task_id)
        if task is None:
            raise AgentRuntimeError("source task is missing")
        remaining = MAX_NEW_CONTACTS_PER_TASK - int(task.get("contact_count", 0))
        if remaining <= 0:
            return {"status": "CONTACT_LIMIT_REACHED", "contacted": 0}
        if requested_target_id:
            requested = await store.get("intent_posts", requested_target_id)
            inspected = [requested] if requested is not None else []
        else:
            inspected = await store.query_documents(
                "intent_posts",
                filters=[("status", "EQUAL", "OPEN")],
                limit=MAX_POSTS_INSPECTED,
            )
        existing = await store.query_documents(
            "candidate_assessments", filters=[("task_id", "EQUAL", task_id)]
        )
        existing_ids = {str(item.get("candidate_intent_id")) for item in existing}
        targets: list[dict[str, Any]] = []
        for candidate in inspected:
            if (
                candidate.get("intent_id") == intent_id
                or candidate.get("owner_uid") == source.get("owner_uid")
                or str(candidate.get("intent_id")) in existing_ids
                or not compatible_posts(source, candidate)
                or await users_blocked(
                    store, str(source["owner_uid"]), str(candidate["owner_uid"])
                )
            ):
                continue
            targets.append(candidate)
            if len(targets) >= min(remaining, MAX_SIMULTANEOUS_NEGOTIATIONS):
                break
        results: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        for candidate in targets:
            invocation_id = stable_id(
                "candidate_invocation",
                intent_id,
                str(candidate["intent_id"]),
                datetime.now(UTC).isoformat(),
            )
            try:
                await consume_daily_agent_turns(
                    store, [str(source["owner_uid"]), str(candidate["owner_uid"])]
                )
                source_runtime, target_runtime = await asyncio.gather(
                    load_personal_agent(store, str(source["owner_agent_id"])),
                    load_personal_agent(store, str(candidate["owner_agent_id"])),
                )
                messages = await negotiate_pair_with_adk(
                    store=store,
                    source_runtime=source_runtime,
                    target_runtime=target_runtime,
                    source_post=source,
                    target_post=candidate,
                )
                results.extend(
                    await record_candidate_exchange(
                        store,
                        source_post=source,
                        target_post=candidate,
                        agent_messages=messages,
                        invocation_id=invocation_id,
                    )
                )
            except Exception as exc:
                failures.append(
                    {
                        "candidate_intent_id": str(candidate.get("intent_id")),
                        "error_type": type(exc).__name__,
                    }
                )
                job_id = stable_id(
                    "job_failure",
                    intent_id,
                    str(candidate.get("intent_id")),
                    invocation_id,
                )
                await store.create(
                    "job_failures",
                    job_id,
                    {
                        "schema_version": SCHEMA_VERSION,
                        "namespace": PRODUCTION_NAMESPACE,
                        "job_id": job_id,
                        "job_type": "CANDIDATE_AGENT_CONTACT",
                        "task_id": task_id,
                        "source_intent_id": intent_id,
                        "target_intent_id": str(candidate.get("intent_id")),
                        "error_type": type(exc).__name__,
                        "status": "RETRYABLE_BY_RECONCILIATION",
                        "created_at": datetime.now(UTC),
                    },
                )
        if not targets:
            clean_task = _clean(task)
            clean_task.update(status="SEARCHING", updated_at=datetime.now(UTC))
            await store.upsert("task_workspaces", task_id, clean_task)
        return {
            "status": "CANDIDATE_POOL_UPDATED" if results else "NO_COMPATIBLE_POST_YET",
            "inspected": len(inspected),
            "contacted": len(results) // 2,
            "failures": failures,
        }
    finally:
        await release_execution_lease(store, lease)


async def set_candidate_state(
    store: MultiUserStore,
    *,
    owner_uid: str,
    task_id: str,
    candidate_intent_id: str,
    state: str,
) -> dict[str, Any]:
    allowed = {"BACKUP", "WITHDRAWN", "PROMISING", "NEEDS_INFORMATION"}
    if state not in allowed:
        raise ValueError("unsupported candidate state")
    assessment_id = _assessment_id(task_id, candidate_intent_id)
    assessment = await store.get("candidate_assessments", assessment_id)
    if assessment is None:
        raise LookupError("candidate assessment was not found")
    if assessment.get("owner_uid") != owner_uid:
        raise PermissionError("candidate assessment is not owned by this account")
    clean = _clean(assessment)
    clean.update(
        state=state,
        last_material_change_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await store.upsert("candidate_assessments", assessment_id, clean)
    await rerank_task_candidates(
        store,
        task_id,
        invocation_id=stable_id(
            "human_candidate_action", owner_uid, task_id, candidate_intent_id, state
        ),
        reason_category="HUMAN_CANDIDATE_CONTROL",
        evidence_ids=[assessment_id],
    )
    return clean
