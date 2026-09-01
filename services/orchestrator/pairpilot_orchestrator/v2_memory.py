"""Scoped, user-controlled Startup V2 Memory retrieval and review."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.multi_user_platform import (
    PRODUCTION_NAMESPACE,
    SCHEMA_VERSION,
    stable_id,
)
from pairpilot_orchestrator.v1_foundation import (
    memory_is_confirmed,
    update_memory_lifecycle,
)

MEMORY_TYPES = {
    "CONFIRMED_USER_MEMORY",
    "TASK_MEMORY",
    "EPISODIC_MEMORY",
    "RELATIONAL_MEMORY",
    "WORKING_BELIEF",
}
TASK_TYPE_SCOPES = {
    "ROOM_SHARE",
    "MEAL_COMPANION",
    "COFFEE_CHAT",
    "EVENT_BUDDY",
    "HACKATHON_TEAMMATE",
}


def _clean(document: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if not key.startswith("_")}


def canonical_memory_type(memory: Mapping[str, Any]) -> str:
    value = str(memory.get("memory_type") or "").upper()
    aliases = {
        "MATCH_OUTCOME": "EPISODIC_MEMORY",
        "EPISODIC_OUTCOME": "EPISODIC_MEMORY",
        "RELATIONSHIP": "RELATIONAL_MEMORY",
        "USER_PREFERENCE": "CONFIRMED_USER_MEMORY",
        "TASK_EXCEPTION": "TASK_MEMORY",
    }
    if value in MEMORY_TYPES:
        return value
    if value in aliases:
        return aliases[value]
    scope = str(memory.get("scope") or "").upper()
    if memory.get("relationship_id") or scope.startswith("RELATIONSHIP"):
        return "RELATIONAL_MEMORY"
    if memory.get("task_id") or scope.startswith("TASK"):
        return "TASK_MEMORY"
    return "CONFIRMED_USER_MEMORY"


def memory_applies(
    memory: Mapping[str, Any],
    *,
    task_id: str | None,
    task_type: str | None,
    relationship_id: str | None,
) -> bool:
    if not memory_is_confirmed(memory):
        return False
    memory_type = canonical_memory_type(memory)
    if memory_type == "WORKING_BELIEF":
        return False
    raw_scope = str(memory.get("scope") or "GLOBAL")
    scope = raw_scope.upper()
    if scope in {"PRIVATE_ONLY", "DO_NOT_USE", "MATCH_HISTORY"}:
        return False
    if memory_type == "EPISODIC_MEMORY" and scope == "GLOBAL":
        return False
    memory_task_id = str(memory.get("task_id") or "")
    if memory_type == "TASK_MEMORY" or scope.startswith("TASK:"):
        scoped_task = raw_scope.split(":", 1)[1] if ":" in raw_scope else memory_task_id
        return bool(task_id and scoped_task == task_id)
    scoped_task_type = str(memory.get("task_type") or "")
    if scope.startswith("TASK_TYPE:"):
        scoped_task_type = scope.split(":", 1)[1]
    if scoped_task_type:
        return bool(task_type and scoped_task_type == task_type.upper())
    if scope in TASK_TYPE_SCOPES:
        return bool(task_type and scope == task_type.upper())
    scoped_relationship = str(memory.get("relationship_id") or "")
    if scope.startswith("RELATIONSHIP:"):
        scoped_relationship = raw_scope.split(":", 1)[1]
    if memory_type == "RELATIONAL_MEMORY" or scoped_relationship:
        return bool(relationship_id and scoped_relationship == relationship_id)
    return scope in {
        "GLOBAL",
        "ABOUT_ME",
        "PREFERENCES",
        "BOUNDARIES",
        "ROUTINES",
        "COMMUNICATION",
    }


def _category(memory: Mapping[str, Any], *, recently_used: bool) -> str:
    status = str(
        memory.get("status") or memory.get("confirmation_status") or "PROPOSED"
    )
    if status in {"ARCHIVED", "REJECTED"} or memory.get("archived"):
        return "ARCHIVED"
    if status != "CONFIRMED":
        return "WAITING_FOR_CONFIRMATION"
    if recently_used:
        return "RECENTLY_USED"
    memory_type = canonical_memory_type(memory)
    if memory_type == "TASK_MEMORY":
        return "TASK_SPECIFIC"
    if memory_type == "RELATIONAL_MEMORY":
        return "RELATIONSHIPS"
    explicit = str(memory.get("category") or "").upper()
    if explicit in {
        "ABOUT_ME",
        "PREFERENCES",
        "BOUNDARIES",
        "ROUTINES",
        "COMMUNICATION",
    }:
        return explicit
    scope = str(memory.get("scope") or "").upper()
    if scope in {"ABOUT_ME", "BOUNDARIES", "ROUTINES", "COMMUNICATION"}:
        return scope
    return "PREFERENCES"


async def _owned_memory(
    store: Any, principal: AuthenticatedPrincipal, memory_id: str
) -> dict[str, Any]:
    memory = await store.get("memories", memory_id)
    if (
        memory is None
        or memory.get("namespace") != PRODUCTION_NAMESPACE
        or memory.get("owner_uid") != principal.uid
    ):
        raise LookupError("memory was not found")
    return memory


def _projection(
    memory: Mapping[str, Any], usage_events: list[Mapping[str, Any]]
) -> dict[str, Any]:
    recent = sorted(
        usage_events, key=lambda event: str(event.get("created_at") or ""), reverse=True
    )
    return {
        "memory_id": memory.get("memory_id"),
        "content": memory.get("content"),
        "memory_type": canonical_memory_type(memory),
        "category": _category(memory, recently_used=bool(recent)),
        "scope": memory.get("scope") or "GLOBAL",
        "source": memory.get("source") or "unknown",
        "confidence": memory.get("confidence") or "UNSPECIFIED",
        "sensitivity": memory.get("sensitivity") or "PRIVATE",
        "status": memory.get("status")
        or memory.get("confirmation_status")
        or "PROPOSED",
        "confirmation_status": memory.get("confirmation_status"),
        "used_for_matching": bool(memory.get("used_for_matching", False)),
        "disabled": bool(memory.get("disabled", False)),
        "last_used_task": recent[0].get("task_id") if recent else None,
        "usage_count": len(recent),
        "created_at": memory.get("created_at"),
        "updated_at": memory.get("updated_at"),
        "provenance_event_ids": list(memory.get("provenance_event_ids") or []),
        "contradicts_memory_ids": list(memory.get("contradicts_memory_ids") or []),
    }


async def list_memory_workspace(
    store: Any, principal: AuthenticatedPrincipal
) -> dict[str, Any]:
    memories, usage_events = await asyncio.gather(
        store.query_documents(
            "memories", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
        store.query_documents(
            "memory_usage_events", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
    )
    usage_by_memory: dict[str, list[Mapping[str, Any]]] = {}
    for event in usage_events:
        usage_by_memory.setdefault(str(event.get("memory_id")), []).append(event)
    projections = [
        _projection(memory, usage_by_memory.get(str(memory.get("memory_id")), []))
        for memory in memories
        if memory.get("namespace") == PRODUCTION_NAMESPACE
    ]
    groups = {
        category: [item for item in projections if item["category"] == category]
        for category in (
            "ABOUT_ME",
            "PREFERENCES",
            "BOUNDARIES",
            "ROUTINES",
            "COMMUNICATION",
            "TASK_SPECIFIC",
            "RELATIONSHIPS",
            "WAITING_FOR_CONFIRMATION",
            "RECENTLY_USED",
            "ARCHIVED",
        )
    }
    return {"memories": projections, "groups": groups, "count": len(projections)}


async def get_memory_detail(
    store: Any, principal: AuthenticatedPrincipal, memory_id: str
) -> dict[str, Any]:
    memory = await _owned_memory(store, principal, memory_id)
    usage_events = await store.query_documents(
        "memory_usage_events", filters=[("memory_id", "EQUAL", memory_id)]
    )
    owned_usage = [
        event for event in usage_events if event.get("owner_uid") == principal.uid
    ]
    return {
        "memory": _projection(memory, owned_usage),
        "usage_events": [
            {
                key: value
                for key, value in event.items()
                if key
                in {
                    "usage_id",
                    "task_id",
                    "task_type",
                    "relationship_id",
                    "purpose",
                    "reason",
                    "created_at",
                }
            }
            for event in sorted(
                owned_usage,
                key=lambda item: str(item.get("created_at") or ""),
                reverse=True,
            )
        ],
        "why_this_was_used": [
            {
                "usage_id": event.get("usage_id"),
                "explanation": (
                    "This action used a confirmed Memory within its recorded scope: "
                    f"{event.get('reason') or 'scope matched the active context'}."
                ),
            }
            for event in owned_usage
        ],
    }


async def retrieve_memory_context(
    store: Any,
    principal: AuthenticatedPrincipal,
    *,
    task_id: str | None,
    relationship_id: str | None = None,
    purpose: str,
    query: str | None = None,
) -> list[dict[str, Any]]:
    task = await store.get("task_workspaces", task_id) if task_id else None
    if task_id and (task is None or task.get("owner_uid") != principal.uid):
        raise LookupError("task was not found")
    task_type = str((task or {}).get("task_type") or "") or None
    memories = await store.query_documents(
        "memories", filters=[("owner_uid", "EQUAL", principal.uid)]
    )
    needle = str(query or "").casefold()
    eligible = [
        memory
        for memory in memories
        if memory.get("namespace") == PRODUCTION_NAMESPACE
        and memory_applies(
            memory,
            task_id=task_id,
            task_type=task_type,
            relationship_id=relationship_id,
        )
        and (not needle or needle in str(memory.get("content") or "").casefold())
    ]
    task_exceptions = {
        str(memory.get("topic_key"))
        for memory in eligible
        if canonical_memory_type(memory) == "TASK_MEMORY" and memory.get("topic_key")
    }
    eligible = [
        memory
        for memory in eligible
        if not (
            canonical_memory_type(memory) == "CONFIRMED_USER_MEMORY"
            and memory.get("topic_key") in task_exceptions
        )
    ]
    result: list[dict[str, Any]] = []
    for memory in eligible[:20]:
        memory_id = str(memory.get("memory_id"))
        usage_id = f"memory_usage_{uuid4().hex}"
        usage = {
            "schema_version": SCHEMA_VERSION,
            "namespace": PRODUCTION_NAMESPACE,
            "usage_id": usage_id,
            "memory_id": memory_id,
            "owner_uid": principal.uid,
            "task_id": task_id,
            "task_type": task_type,
            "relationship_id": relationship_id,
            "purpose": purpose,
            "reason": (
                f"confirmed status and scope {memory.get('scope') or 'GLOBAL'} matched"
            ),
            "created_at": datetime.now(UTC),
        }
        await store.create("memory_usage_events", usage_id, usage)
        result.append(
            {
                "memory_id": memory_id,
                "content": memory.get("content"),
                "memory_type": canonical_memory_type(memory),
                "scope": memory.get("scope") or "GLOBAL",
                "usage_id": usage_id,
                "why_used": usage["reason"],
            }
        )
    return result


async def apply_memory_action(
    store: Any,
    principal: AuthenticatedPrincipal,
    *,
    memory_id: str,
    action: str,
    content: str | None,
    scope: str | None,
) -> dict[str, Any]:
    memory = await _owned_memory(store, principal, memory_id)
    if action in {"CONFIRM", "EDIT_AND_CONFIRM"}:
        conflict_ids = [str(item) for item in memory.get("contradicts_memory_ids", [])]
        conflicts = await asyncio.gather(
            *(store.get("memories", conflict_id) for conflict_id in conflict_ids)
        )
        active_conflicts = [
            item
            for item in conflicts
            if item is not None
            and item.get("owner_uid") == principal.uid
            and memory_is_confirmed(item)
        ]
        if active_conflicts:
            timestamp = datetime.now(UTC)
            clean = _clean(memory)
            clean.update(confirmation_status="NEEDS_REVIEW", updated_at=timestamp)
            await store.upsert("memories", memory_id, clean)
            decision_id = stable_id(
                "decision_memory_conflict", principal.uid, memory_id
            )
            await store.create(
                "decisions",
                decision_id,
                {
                    "schema_version": SCHEMA_VERSION,
                    "namespace": PRODUCTION_NAMESPACE,
                    "decision_id": decision_id,
                    "owner_uid": principal.uid,
                    "type": "CONFIRM_MEMORY",
                    "status": "OPEN",
                    "title": "Review conflicting Memory",
                    "summary": "This proposed Memory conflicts with confirmed Memory.",
                    "entity_ids": [memory_id, *conflict_ids],
                    "priority": "HIGH",
                    "created_at": timestamp,
                },
            )
            raise ValueError("conflicting confirmed Memory requires review")
    updated = await update_memory_lifecycle(
        store,
        principal,
        memory_id,
        action=action,
        content=content,
        scope=scope,
    )
    return _clean(updated)
