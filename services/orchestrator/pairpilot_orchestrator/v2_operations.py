"""Role-protected, privacy-bounded Startup V2 operations services.

Operator projections deliberately omit authentication emails, conversation text,
Post private projections, Memory contents, and model prompts/responses. Mutations
are explicit, bounded, idempotent where retry semantics matter, and audited.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pairpilot_orchestrator.auth.authorization import require_admin
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.multi_user_platform import (
    PRODUCTION_NAMESPACE,
    MultiUserStore,
    stable_id,
)

MAX_ADMIN_ROWS = 100
ACTIVE_REPORT_STATES = {"OPEN", "ACKNOWLEDGED", "IN_REVIEW"}
RETRYABLE_JOB_STATES = {"FAILED", "DEAD_LETTER", "RETRY_FAILED"}
LIFECYCLE_EVENT_NAMES = {
    "account.created": "account_created",
    "onboarding.completed": "onboarding_completed",
    "community.joined": "community_joined",
    "task.created": "request_created",
    "post.drafted": "post_drafted",
    "post.published": "post_published",
    "candidate.discovered": "candidate_discovered",
    "agent.contact.initiated": "agent_contact_initiated",
    "a2a.message.received": "peer_response_received",
    "candidate.ranking.changed": "ranking_changed",
    "room.created": "room_created",
    "proposal.created": "proposal_ready",
    "human.approval.received": "human_approval_received",
    "match.confirmed": "match_confirmed",
    "match.completed": "plan_completed",
    "match.cancelled": "plan_cancelled",
    "connection.used": "connection_reused",
    "memory.proposed": "memory_proposed",
    "memory.confirmed": "memory_confirmed",
}


def _clean(document: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if not key.startswith("_")}


def _event_type(event: Mapping[str, Any]) -> str:
    return str(event.get("event_type") or event.get("eventType") or "")


def _safe_time(value: object) -> object:
    return value if isinstance(value, (str, datetime)) else None


async def _audit(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    action: str,
    target_type: str,
    target_id: str,
    outcome: str,
    reason: str | None = None,
) -> str:
    audit_id = f"audit_{uuid4().hex}"
    await store.create(
        "audit_events",
        audit_id,
        {
            "schema_version": 4,
            "namespace": PRODUCTION_NAMESPACE,
            "audit_id": audit_id,
            "actor_uid": principal.uid,
            "actor_role": "ADMIN" if principal.admin else "COMMUNITY_MODERATOR",
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "outcome": outcome,
            "reason": reason,
            "created_at": datetime.now(UTC),
        },
    )
    return audit_id


async def build_operations_console(
    store: MultiUserStore, principal: AuthenticatedPrincipal
) -> dict[str, Any]:
    """Return all admin sections as bounded, content-free operational projections."""

    require_admin(principal)
    collections = (
        "users",
        "communities",
        "intent_posts",
        "reports",
        "moderation_actions",
        "agent_invocations",
        "agent_runs",
        "job_failures",
        "dead_letter_messages",
        "usage_quotas",
        "account_deletion_requests",
        "account_deletion_jobs",
        "audit_events",
        "events",
        "task_workspaces",
        "candidate_assessments",
        "proposals",
        "human_approvals",
        "matches",
        "outcomes",
        "relationship_usage_events",
        "memories",
    )
    data = {
        name: await store.query_documents(name, filters=[], limit=MAX_ADMIN_ROWS)
        for name in collections
    }
    events_by_name = Counter(_event_type(item) for item in data["events"])
    lifecycle = {
        metric: sum(
            count
            for event_name, count in events_by_name.items()
            if canonical in event_name.casefold()
        )
        for canonical, metric in LIFECYCLE_EVENT_NAMES.items()
    }
    agent_runs = [*data["agent_invocations"], *data["agent_runs"]]
    failed_runs = [
        item
        for item in agent_runs
        if str(item.get("status") or "").upper() in {"FAILED", "ERROR"}
        or item.get("error_type")
        or item.get("error")
    ]
    latencies = [
        float(item.get("latency_ms", item.get("latencyMs", 0)))
        for item in agent_runs
        if isinstance(item.get("latency_ms", item.get("latencyMs")), (int, float))
    ]
    unpublished_events = sum(item.get("published") is False for item in data["events"])
    dlq_open = sum(
        str(item.get("status") or "OPEN").upper() not in {"DISMISSED", "RESOLVED"}
        for item in data["dead_letter_messages"]
    )
    revision = os.getenv("K_REVISION") or "LOCAL_OR_UNKNOWN"
    worker_revision = os.getenv("PAIRPILOT_WORKER_REVISION")
    return {
        "generated_at": datetime.now(UTC),
        "access": "SERVER_VERIFIED_ADMIN_CLAIM",
        "privacy_notice": (
            "Authentication emails, private Posts, conversation text, Memory "
            "contents, prompts, and model responses are excluded."
        ),
        "system_health": {
            "api_status": "UP",
            "cloud_run_revision": revision,
            "worker_status": "CONFIGURED" if worker_revision else "NOT_REPORTED",
            "worker_revision": worker_revision,
            "pubsub_backlog": unpublished_events,
            "dlq_count": dlq_open,
            "recent_error_count": len(failed_runs),
            "model_failure_rate": (
                len(failed_runs) / len(agent_runs) if agent_runs else None
            ),
            "average_agent_latency_ms": (
                sum(latencies) / len(latencies) if latencies else None
            ),
            "firestore_transaction_failures": events_by_name.get(
                "firestore.transaction.failed", 0
            ),
            "pubsub_provider_metrics": "NOT_CONFIGURED_IN_PROCESS",
        },
        "counts": {
            "users": len(data["users"]),
            "active_users": sum(
                str(item.get("account_status") or "ACTIVE") == "ACTIVE"
                for item in data["users"]
            ),
            "communities": len(data["communities"]),
            "posts": len(data["intent_posts"]),
            "open_reports": sum(
                str(item.get("status") or "OPEN") in ACTIVE_REPORT_STATES
                for item in data["reports"]
            ),
            "failed_jobs": len(data["job_failures"]),
            "deletion_requests": len(data["account_deletion_requests"]),
        },
        "users": [
            {
                "uid": item.get("uid") or item.get("owner_uid"),
                "display_name": item.get("display_name") or "Member",
                "account_status": item.get("account_status") or "ACTIVE",
                "onboarding_status": item.get("onboarding_status"),
                "created_at": _safe_time(item.get("created_at")),
            }
            for item in data["users"]
        ],
        "communities": [
            {
                "community_id": item.get("community_id"),
                "name": item.get("name"),
                "status": item.get("status"),
                "membership_type": item.get("membership_type")
                or item.get("membership_policy"),
            }
            for item in data["communities"]
        ],
        "posts": [
            {
                "intent_id": item.get("intent_id"),
                "community_id": item.get("community_id"),
                "intent_type": item.get("intent_type"),
                "status": item.get("status"),
                "updated_at": _safe_time(item.get("updated_at")),
            }
            for item in data["intent_posts"]
        ],
        "reports": [_report_summary(item) for item in data["reports"]],
        "moderation": [
            {
                "action_id": item.get("action_id"),
                "action": item.get("action"),
                "target_type": item.get("target_type"),
                "target_id": item.get("target_id"),
                "created_at": _safe_time(item.get("created_at")),
            }
            for item in data["moderation_actions"]
        ],
        "agent_runs": [
            {
                "run_id": item.get("run_id") or item.get("invocation_id"),
                "status": item.get("status")
                or ("FAILED" if item.get("error") else "OK"),
                "model_id": item.get("model_id") or item.get("modelId"),
                "latency_ms": item.get("latency_ms") or item.get("latencyMs"),
                "retry_count": item.get("retry_count") or item.get("retryCount", 0),
                "task_type": item.get("task_type"),
                "created_at": _safe_time(
                    item.get("created_at") or item.get("createdAt")
                ),
            }
            for item in agent_runs[-MAX_ADMIN_ROWS:]
        ],
        "failed_jobs": [_job_summary(item) for item in data["job_failures"]],
        "dead_letters": [_dlq_summary(item) for item in data["dead_letter_messages"]],
        "model_usage": _model_usage(agent_runs),
        "quotas": [_quota_summary(item) for item in data["usage_quotas"]],
        "account_deletions": [
            {
                "request_id": item.get("request_id") or item.get("job_id"),
                "owner_uid": item.get("owner_uid"),
                "status": item.get("status"),
                "requested_at": _safe_time(item.get("requested_at")),
                "private_erasure_after": _safe_time(item.get("private_erasure_after")),
            }
            for item in [
                *data["account_deletion_requests"],
                *data["account_deletion_jobs"],
            ]
        ],
        "analytics": _analytics(data, lifecycle),
        "audit": [
            {
                "audit_id": item.get("audit_id"),
                "actor_role": item.get("actor_role"),
                "action": item.get("action"),
                "target_type": item.get("target_type"),
                "target_id": item.get("target_id"),
                "outcome": item.get("outcome"),
                "created_at": _safe_time(item.get("created_at")),
            }
            for item in data["audit_events"]
        ],
    }


def _report_summary(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "report_id": item.get("report_id"),
        "target_type": item.get("target_type"),
        "target_id": item.get("target_id"),
        "community_id": item.get("community_id"),
        "category": item.get("category"),
        "status": item.get("status") or "OPEN",
        "details_available": bool(str(item.get("details") or "").strip()),
        "created_at": _safe_time(item.get("created_at")),
    }


def _job_summary(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "job_id": item.get("job_id") or item.get("failure_id"),
        "task_id": item.get("task_id"),
        "job_type": item.get("job_type") or item.get("event_type"),
        "error_type": item.get("error_type") or "UNCLASSIFIED",
        "status": item.get("status") or "FAILED",
        "attempt_count": int(item.get("attempt_count", item.get("retry_count", 0))),
        "created_at": _safe_time(item.get("created_at")),
        "last_attempt_at": _safe_time(item.get("last_attempt_at")),
    }


def _dlq_summary(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "message_id": item.get("message_id") or item.get("dlq_id"),
        "event_id": item.get("event_id"),
        "event_type": item.get("event_type"),
        "task_id": item.get("task_id"),
        "status": item.get("status") or "OPEN",
        "delivery_attempts": item.get("delivery_attempts"),
        "created_at": _safe_time(item.get("created_at")),
    }


def _quota_summary(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "owner_uid": item.get("owner_uid") or item.get("uid"),
        "active_task_limit": item.get("active_task_limit"),
        "concurrent_negotiations_per_task": item.get(
            "concurrent_negotiations_per_task"
        ),
        "new_contacts_per_task": item.get("new_contacts_per_task"),
        "daily_agent_turn_limit": item.get("daily_agent_turn_limit"),
        "agent_turns_today": item.get("agent_turns_today", 0),
        "quota_date": item.get("quota_date"),
    }


def _model_usage(agent_runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    def tokens(item: Mapping[str, Any], direction: str) -> int:
        direct = item.get(f"{direction}_tokens")
        if isinstance(direct, int):
            return direct
        usage = item.get("token_usage") or item.get("tokenUsage")
        if not isinstance(usage, Mapping):
            return 0
        value = usage.get(direction) or usage.get(f"{direction}_tokens")
        return int(value) if isinstance(value, (int, float)) else 0

    input_tokens = sum(tokens(item, "input") for item in agent_runs)
    output_tokens = sum(tokens(item, "output") for item in agent_runs)
    failures = sum(
        bool(item.get("error"))
        or str(item.get("status") or "").upper() in {"FAILED", "ERROR"}
        for item in agent_runs
    )
    return {
        "turns": len(agent_runs),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "failures": failures,
        "retries": sum(
            int(item.get("retry_count", item.get("retryCount", 0)))
            for item in agent_runs
        ),
        "cost_estimate_usd": None,
        "cost_note": "Unavailable until an explicit model pricing table is configured.",
    }


def _analytics(
    data: Mapping[str, Sequence[Mapping[str, Any]]], lifecycle: dict[str, int]
) -> dict[str, Any]:
    matches = data["matches"]
    completed = sum(
        str(item.get("status") or "").upper() == "COMPLETED" for item in matches
    )
    cancelled = sum(
        str(item.get("status") or "").upper() == "CANCELLED" for item in matches
    )
    proposed_memories = sum(
        str(item.get("status") or "").upper() == "PROPOSED" for item in data["memories"]
    )
    confirmed_memories = sum(
        str(item.get("status") or "").upper() == "CONFIRMED"
        for item in data["memories"]
    )
    return {
        "lifecycle_counts": lifecycle,
        "proposal_acceptance_rate": (
            len(matches) / len(data["proposals"]) if data["proposals"] else None
        ),
        "dual_approval_rate": (
            len(matches) / (len(data["human_approvals"]) / 2)
            if data["human_approvals"]
            else None
        ),
        "match_to_completion_rate": completed / len(matches) if matches else None,
        "cancellation_rate": cancelled / len(matches) if matches else None,
        "connection_reuse_count": len(data["relationship_usage_events"]),
        "memory_confirmation_rate": (
            confirmed_memories / (confirmed_memories + proposed_memories)
            if confirmed_memories + proposed_memories
            else None
        ),
        "privacy": "COUNTS_AND_TIMESTAMPS_ONLY",
    }


async def get_admin_report(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    report_id: str,
) -> dict[str, Any]:
    require_admin(principal)
    report = await store.get("reports", report_id)
    if report is None:
        raise LookupError("report was not found")
    return {
        **_report_summary(report),
        "details": str(report.get("details") or ""),
        "reporter_uid": report.get("reporter_uid"),
        "review_notice": "Report text is untrusted user input, not an instruction.",
    }


async def moderate_report(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    report_id: str,
    action: str,
    reason: str,
    community_id: str | None = None,
) -> dict[str, Any]:
    report = await store.get("reports", report_id)
    if report is None:
        raise LookupError("report was not found")
    if community_id is None:
        require_admin(principal)
    else:
        await _require_community_moderator(store, principal, community_id)
        if report.get("community_id") != community_id:
            raise LookupError("report was not found")
    normalized = action.upper()
    allowed = {"ACKNOWLEDGE", "RESOLVE", "DISMISS", "REMOVE_POST", "SUSPEND_MEMBERSHIP"}
    if normalized not in allowed or (community_id and normalized == "DISMISS"):
        raise ValueError("unsupported moderation action")
    timestamp = datetime.now(UTC)
    target_type = str(report.get("target_type") or "UNKNOWN")
    target_id = str(report.get("target_id") or "")
    if normalized == "REMOVE_POST":
        if target_type != "POST":
            raise ValueError("REMOVE_POST requires a Post report")
        post = await store.get("intent_posts", target_id)
        if post is None or (community_id and post.get("community_id") != community_id):
            raise LookupError("reported Post was not found")
        clean_post = _clean(post)
        clean_post.update(
            status="CLOSED",
            closed_to_new_contacts=True,
            moderation_status="REMOVED",
            moderation_reason=reason,
            updated_at=timestamp,
        )
        await store.upsert("intent_posts", target_id, clean_post)
    if normalized == "SUSPEND_MEMBERSHIP":
        target_uid = str(report.get("target_owner_uid") or target_id)
        target_community = community_id or str(report.get("community_id") or "")
        if not target_uid or not target_community:
            raise ValueError("the report has no Community membership target")
        memberships = await store.query_documents(
            "community_memberships", filters=[("owner_uid", "EQUAL", target_uid)]
        )
        membership = next(
            (
                item
                for item in memberships
                if item.get("community_id") == target_community
            ),
            None,
        )
        if membership is None:
            raise LookupError("Community membership was not found")
        clean_membership = _clean(membership)
        clean_membership.update(status="SUSPENDED", updated_at=timestamp)
        await store.upsert(
            "community_memberships",
            str(membership.get("membership_id") or membership.get("_id")),
            clean_membership,
        )
    status = {
        "ACKNOWLEDGE": "ACKNOWLEDGED",
        "DISMISS": "DISMISSED",
    }.get(normalized, "RESOLVED")
    clean_report = _clean(report)
    clean_report.update(
        status=status,
        resolution_action=normalized,
        resolved_by_uid=principal.uid,
        resolved_at=timestamp if status in {"RESOLVED", "DISMISSED"} else None,
        updated_at=timestamp,
    )
    await store.upsert("reports", report_id, clean_report)
    action_id = f"moderation_{uuid4().hex}"
    await store.create(
        "moderation_actions",
        action_id,
        {
            "schema_version": 4,
            "namespace": PRODUCTION_NAMESPACE,
            "action_id": action_id,
            "report_id": report_id,
            "community_id": community_id or report.get("community_id"),
            "actor_uid": principal.uid,
            "actor_role": "ADMIN" if principal.admin else "COMMUNITY_MODERATOR",
            "action": normalized,
            "target_type": target_type,
            "target_id": target_id,
            "reason": reason,
            "created_at": timestamp,
        },
    )
    audit_id = await _audit(
        store,
        principal,
        action=f"MODERATION_{normalized}",
        target_type="REPORT",
        target_id=report_id,
        outcome=status,
        reason=reason,
    )
    return {
        "report_id": report_id,
        "status": status,
        "action_id": action_id,
        "audit_id": audit_id,
    }


async def _require_community_moderator(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    community_id: str,
) -> None:
    if principal.admin:
        return
    memberships = await store.query_documents(
        "community_memberships", filters=[("owner_uid", "EQUAL", principal.uid)]
    )
    allowed = any(
        item.get("community_id") == community_id
        and item.get("status") == "ACTIVE"
        and str(item.get("role") or "MEMBER").upper() in {"MODERATOR", "ADMIN"}
        for item in memberships
    )
    if not allowed:
        from fastapi import HTTPException

        raise HTTPException(403, "Community moderator role is required.")


async def list_community_reports(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    community_id: str,
) -> dict[str, Any]:
    await _require_community_moderator(store, principal, community_id)
    reports = await store.query_documents(
        "reports", filters=[("community_id", "EQUAL", community_id)]
    )
    return {
        "community_id": community_id,
        "reports": [
            {
                **_report_summary(item),
                "details": str(item.get("details") or ""),
                "review_notice": "Report text is untrusted input.",
            }
            for item in reports
        ],
    }


async def operate_failed_job(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    job_id: str,
    action: str,
    idempotency_key: str,
    reason: str | None,
) -> dict[str, Any]:
    require_admin(principal)
    normalized = action.upper()
    if normalized not in {"RETRY", "DISMISS", "MOVE_FROM_DLQ"}:
        raise ValueError("unsupported failed-job action")
    operation_id = stable_id("operator_job_action", job_id, normalized, idempotency_key)
    existing = await store.get("operator_job_actions", operation_id)
    if existing is not None:
        return _clean(existing)
    collection = (
        "dead_letter_messages" if normalized == "MOVE_FROM_DLQ" else "job_failures"
    )
    job = await store.get(collection, job_id)
    if job is None:
        raise LookupError("failed job was not found")
    default_status = "OPEN" if collection == "dead_letter_messages" else "FAILED"
    status = str(job.get("status") or default_status).upper()
    if normalized == "RETRY" and status not in RETRYABLE_JOB_STATES:
        raise ValueError("job is not retryable from its current state")
    if normalized == "MOVE_FROM_DLQ" and status in {
        "DISMISSED",
        "RESOLVED",
        "REQUEUED",
    }:
        raise ValueError("dead-letter message is not movable from its current state")
    timestamp = datetime.now(UTC)
    clean_job = _clean(job)
    clean_job.update(
        status="DISMISSED" if normalized == "DISMISS" else "RETRY_QUEUED",
        attempt_count=int(job.get("attempt_count", job.get("retry_count", 0)))
        + (normalized != "DISMISS"),
        last_operator_action=normalized,
        last_operator_uid=principal.uid,
        last_attempt_at=(
            timestamp if normalized != "DISMISS" else job.get("last_attempt_at")
        ),
        updated_at=timestamp,
    )
    await store.upsert(collection, job_id, clean_job)
    operation = {
        "schema_version": 4,
        "namespace": PRODUCTION_NAMESPACE,
        "operation_id": operation_id,
        "job_id": job_id,
        "collection": collection,
        "action": normalized,
        "status": clean_job["status"],
        "reason": reason,
        "actor_uid": principal.uid,
        "created_at": timestamp,
    }
    created = await store.create("operator_job_actions", operation_id, operation)
    if not created:
        replay = await store.get("operator_job_actions", operation_id)
        return _clean(replay or operation)
    if normalized != "DISMISS":
        await store.write_event(
            event_type="operations.job.retry.requested.v2",
            run_id=job_id,
            producer=principal.uid,
            payload={
                "jobId": job_id,
                "sourceCollection": collection,
                "operationId": operation_id,
            },
            idempotency_key=f"v2:{operation_id}:retry",
        )
    operation["audit_id"] = await _audit(
        store,
        principal,
        action=f"FAILED_JOB_{normalized}",
        target_type=collection.upper(),
        target_id=job_id,
        outcome=str(clean_job["status"]),
        reason=reason,
    )
    return operation


async def update_user_quota(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    owner_uid: str,
    values: Mapping[str, int],
    reason: str,
) -> dict[str, Any]:
    require_admin(principal)
    quota = await store.get("usage_quotas", owner_uid)
    if quota is None:
        raise LookupError("usage quota was not found")
    clean = _clean(quota)
    clean.update(values)
    clean.update(updated_at=datetime.now(UTC), updated_by_uid=principal.uid)
    await store.upsert("usage_quotas", owner_uid, clean)
    audit_id = await _audit(
        store,
        principal,
        action="QUOTA_UPDATED",
        target_type="USAGE_QUOTA",
        target_id=owner_uid,
        outcome="UPDATED",
        reason=reason,
    )
    return {**_quota_summary(clean), "audit_id": audit_id}
