"""Admin-only operational and privacy-safe product analytics projections."""

from __future__ import annotations

from datetime import UTC, datetime
from statistics import mean
from typing import Any

from pairpilot_orchestrator.auth.authorization import require_admin
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.multi_user_platform import MultiUserStore


def _seconds(start: object, end: object) -> float | None:
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        return None
    return max(0.0, (end.astimezone(UTC) - start.astimezone(UTC)).total_seconds())


async def build_admin_dashboard(
    store: MultiUserStore, principal: AuthenticatedPrincipal
) -> dict[str, Any]:
    """Return aggregates without private messages, goals, feedback, or Memory."""

    require_admin(principal)
    collection_names = [
        "users",
        "intent_posts",
        "reports",
        "blocks",
        "communities",
        "agent_invocations",
        "job_failures",
        "dead_letter_messages",
        "usage_quotas",
        "rate_limit_events",
        "moderation_signals",
        "account_deletion_jobs",
        "events",
        "task_workspaces",
        "candidate_assessments",
        "proposals",
        "human_approvals",
        "matches",
        "outcomes",
        "memories",
    ]
    data = {
        name: await store.query_documents(name, filters=[], limit=1_000)
        for name in collection_names
    }
    tasks_by_id = {str(item.get("task_id")): item for item in data["task_workspaces"]}
    first_candidate_by_task: dict[str, datetime] = {}
    for candidate in data["candidate_assessments"]:
        created = candidate.get("created_at")
        task_id = str(candidate.get("task_id", ""))
        if isinstance(created, datetime) and (
            task_id not in first_candidate_by_task
            or created < first_candidate_by_task[task_id]
        ):
            first_candidate_by_task[task_id] = created
    candidate_latencies = [
        seconds
        for task_id, candidate_time in first_candidate_by_task.items()
        if (
            seconds := _seconds(
                tasks_by_id.get(task_id, {}).get("created_at"), candidate_time
            )
        )
        is not None
    ]
    proposal_latencies = [
        seconds
        for proposal in data["proposals"]
        if (
            seconds := _seconds(
                tasks_by_id.get(str(proposal.get("source_task_id")), {}).get(
                    "created_at"
                ),
                proposal.get("created_at"),
            )
        )
        is not None
    ]
    matches = data["matches"]
    approvals = data["human_approvals"]
    committed_proposal_ids = {str(item.get("proposal_id")) for item in matches}
    matched_contacts = [
        int(task.get("contact_count", 0))
        for task in data["task_workspaces"]
        if str(task.get("match_id", "")) in committed_proposal_ids
    ]
    confirmed_memories = sum(
        item.get("status") == "CONFIRMED" for item in data["memories"]
    )
    proposed_memories = sum(
        item.get("status") == "PROPOSED" for item in data["memories"]
    )
    events_unpublished = sum(item.get("published") is False for item in data["events"])
    return {
        "generated_at": datetime.now(UTC),
        "access": "EXPLICIT_ADMIN_CLAIM",
        "health": {
            "api": "UP",
            "firestore": "UP",
            "unpublished_event_backlog": events_unpublished,
            "dead_letter_messages": len(data["dead_letter_messages"]),
            "failed_jobs": len(data["job_failures"]),
        },
        "counts": {
            "users": len(data["users"]),
            "active_users": sum(
                item.get("account_status") == "ACTIVE" for item in data["users"]
            ),
            "public_posts": len(data["intent_posts"]),
            "open_posts": sum(
                item.get("status") == "OPEN" for item in data["intent_posts"]
            ),
            "reports_open": sum(
                item.get("status") == "OPEN" for item in data["reports"]
            ),
            "blocks": len(data["blocks"]),
            "communities": len(data["communities"]),
            "agent_runs": len(data["agent_invocations"]),
            "moderation_queue": len(data["moderation_signals"]),
            "account_deletion_queue": len(data["account_deletion_jobs"]),
        },
        "model_usage": {
            "daily_agent_turns": sum(
                int(item.get("agent_turns_today", 0)) for item in data["usage_quotas"]
            ),
            "input_tokens": sum(
                int(item.get("input_tokens", 0)) for item in data["agent_invocations"]
            ),
            "output_tokens": sum(
                int(item.get("output_tokens", 0)) for item in data["agent_invocations"]
            ),
        },
        "analytics": {
            "time_to_first_qualified_candidate_seconds": (
                mean(candidate_latencies) if candidate_latencies else None
            ),
            "time_to_proposal_seconds": (
                mean(proposal_latencies) if proposal_latencies else None
            ),
            "mutual_approval_rate": (
                len(matches) / len(data["proposals"]) if data["proposals"] else None
            ),
            "match_completion_rate": (
                sum(item.get("did_plan_happen") is True for item in data["outcomes"])
                / len(matches)
                if matches
                else None
            ),
            "average_agent_contacts_per_successful_match": (
                mean(matched_contacts) if matched_contacts else None
            ),
            "background_discovery_count": len(data["candidate_assessments"]),
            "user_intervention_count": len(approvals),
            "memory_confirmation_rate": (
                confirmed_memories / (confirmed_memories + proposed_memories)
                if confirmed_memories + proposed_memories
                else None
            ),
        },
        "queues": {
            "reports": [
                {
                    "report_id": item.get("report_id"),
                    "target_type": item.get("target_type"),
                    "category": item.get("category"),
                    "status": item.get("status"),
                    "created_at": item.get("created_at"),
                }
                for item in data["reports"]
            ],
            "failed_jobs": [
                {
                    "job_id": item.get("job_id"),
                    "error_type": item.get("error_type"),
                    "status": item.get("status"),
                    "created_at": item.get("created_at"),
                }
                for item in data["job_failures"]
            ],
        },
    }
