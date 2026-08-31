"""Low-cost reconciliation for missed events and stale marketplace state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pairpilot_orchestrator.multi_user_platform import (
    PRODUCTION_NAMESPACE,
    MultiUserStore,
    _clean,
)
from pairpilot_orchestrator.v1_candidate_pool import (
    ACTIVE_CANDIDATE_STATES,
    process_candidate_pool_event,
    rerank_task_candidates,
)
from pairpilot_orchestrator.v1_foundation import create_notification

MAX_POSTS_PER_RECONCILIATION = 3


def _expired(value: object, now: datetime) -> bool:
    if isinstance(value, datetime):
        return value.astimezone(UTC) <= now
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")) <= now
        except ValueError:
            return False
    return False


async def reconcile_candidate_availability(
    store: MultiUserStore, *, now: datetime
) -> int:
    assessments = await store.query_documents(
        "candidate_assessments",
        filters=[("namespace", "EQUAL", PRODUCTION_NAMESPACE)],
        limit=100,
    )
    changed = 0
    for assessment in assessments:
        if assessment.get("state") not in ACTIVE_CANDIDATE_STATES:
            continue
        candidate_intent_id = str(assessment.get("candidate_intent_id", ""))
        candidate = await store.get("intent_posts", candidate_intent_id)
        next_state = ""
        reason = ""
        if candidate is None or candidate.get("status") == "CLOSED":
            next_state, reason = "CLOSED", "Candidate post closed"
        elif candidate.get("status") == "AWAITING_APPROVAL":
            proposal_id = str(candidate.get("active_proposal_id", ""))
            if proposal_id and proposal_id != str(assessment.get("proposal_id", "")):
                next_state, reason = (
                    "MATCHED_ELSEWHERE",
                    "Candidate entered another proposal",
                )
        elif candidate.get("status") == "PAUSED":
            next_state, reason = "WAITING", "Candidate post paused"
        elif int(candidate.get("capacity_remaining", 0)) <= 0:
            next_state, reason = "MATCHED_ELSEWHERE", "Candidate capacity unavailable"
        elif _expired(candidate.get("expires_at"), now):
            next_state, reason = "CLOSED", "Candidate post expired"
        if not next_state or next_state == assessment.get("state"):
            continue
        clean = _clean(assessment)
        clean.update(
            state=next_state,
            last_material_change_at=now,
            updated_at=now,
        )
        await store.upsert("candidate_assessments", str(clean["assessment_id"]), clean)
        await rerank_task_candidates(
            store,
            str(clean["task_id"]),
            invocation_id=f"reconcile:{clean['assessment_id']}:{next_state}",
            reason_category="CANDIDATE_AVAILABILITY_CHANGED",
            evidence_ids=[candidate_intent_id],
            now=now,
        )
        await create_notification(
            store,
            owner_uid=str(clean["owner_uid"]),
            notification_type="CANDIDATE_CHANGED",
            title="Candidate availability changed",
            body=f"{reason}. Your Agent reranked the remaining options.",
            entity_ids=[str(clean["task_id"]), candidate_intent_id],
            idempotency_key=f"availability:{clean['assessment_id']}:{next_state}",
            now=now,
        )
        changed += 1
    return changed


async def reconcile_stale_holds(store: MultiUserStore, *, now: datetime) -> int:
    holds = await store.query_documents(
        "holds", filters=[("active", "EQUAL", True)], limit=100
    )
    expired_count = 0
    for hold in holds:
        if not _expired(hold.get("expires_at"), now):
            continue
        clean_hold = _clean(hold)
        clean_hold.update(active=False, status="EXPIRED", updated_at=now)
        await store.upsert("holds", str(clean_hold["hold_id"]), clean_hold)
        proposal_id = str(clean_hold.get("proposal_id", ""))
        proposal = await store.get("proposals", proposal_id)
        if proposal is not None and proposal.get("status") == "AWAITING_HUMANS":
            clean_proposal = _clean(proposal)
            clean_proposal.update(status="EXPIRED", updated_at=now)
            await store.upsert("proposals", proposal_id, clean_proposal)
            for uid in proposal.get("participant_uids", []):
                await create_notification(
                    store,
                    owner_uid=str(uid),
                    notification_type="PROPOSAL_EXPIRED",
                    title="A proposal expired",
                    body=(
                        "The temporary capacity hold expired. Ask your Agent to "
                        "revalidate before deciding."
                    ),
                    entity_ids=[proposal_id],
                    idempotency_key=f"proposal-expired:{proposal_id}:{uid}",
                    now=now,
                )
        expired_count += 1
    return expired_count


async def reconcile_open_posts(store: MultiUserStore) -> dict[str, int]:
    posts = await store.query_documents(
        "intent_posts", filters=[("status", "EQUAL", "OPEN")], limit=200
    )
    eligible: list[tuple[float, float, dict[str, Any]]] = []
    for post in posts:
        task = await store.get("task_workspaces", str(post.get("task_id", "")))
        if task is None or int(task.get("contact_count", 0)) >= 5:
            continue
        last_reconciled = task.get("last_reconciled_at")
        published = post.get("published_at")
        eligible.append(
            (
                _as_timestamp(last_reconciled),
                _as_timestamp(published),
                post,
            )
        )
    eligible.sort(key=lambda item: (item[0], item[1], str(item[2].get("intent_id"))))
    attempted = 0
    contacted = 0
    for _, _, post in eligible[:MAX_POSTS_PER_RECONCILIATION]:
        result = await process_candidate_pool_event(store, str(post["intent_id"]))
        attempted += 1
        contacted += int(result.get("contacted", 0))
        task_id = str(post.get("task_id", ""))
        current = await store.get("task_workspaces", task_id)
        if current is not None:
            clean = _clean(current)
            timestamp = datetime.now(UTC)
            clean.update(last_reconciled_at=timestamp, updated_at=timestamp)
            await store.upsert("task_workspaces", task_id, clean)
    return {"posts_attempted": attempted, "candidates_contacted": contacted}


def _as_timestamp(value: object) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
    return 0.0


async def run_v1_reconciliation(
    store: MultiUserStore, *, now: datetime | None = None
) -> dict[str, Any]:
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    availability_changed = await reconcile_candidate_availability(store, now=timestamp)
    holds_expired = await reconcile_stale_holds(store, now=timestamp)
    open_post_result = await reconcile_open_posts(store)
    return {
        "status": "RECONCILED",
        "availability_changed": availability_changed,
        "holds_expired": holds_expired,
        **open_post_result,
        "completed_at": timestamp,
    }
