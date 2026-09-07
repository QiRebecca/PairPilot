"""Decision, notification, and action-specific autonomy product glue."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.multi_user_commit import (
    MultiUserCommitError,
    approve_multi_user_proposal,
)
from pairpilot_orchestrator.multi_user_platform import (
    PRODUCTION_NAMESPACE,
    SCHEMA_VERSION,
    stable_id,
)
from pairpilot_orchestrator.v2_matches import approve_match_change
from pairpilot_orchestrator.v2_memory import apply_memory_action

ACTION_DEFAULTS = {
    "DRAFT_POST": "AUTOMATIC",
    "PUBLISH_POST": "ASK_FIRST",
    "SEARCH_POSTS": "AUTOMATIC",
    "CONTACT_PERSONAL_AGENTS": "ASK_FIRST",
    "ASK_COMPATIBILITY_QUESTIONS": "AUTOMATIC",
    "NEGOTIATE_SOFT_PREFERENCES": "AUTOMATIC",
    "PLACE_TEMPORARY_HOLDS": "ASK_FIRST",
    "OPEN_AGENT_ROOMS": "AUTOMATIC",
    "DRAFT_SHARED_MESSAGES": "AUTOMATIC",
    "SEND_SHARED_MESSAGES": "ASK_FIRST",
    "SHARE_PROTECTED_INFORMATION": "NEVER",
    "APPROVE_FINAL_COMMITMENT": "ASK_FIRST",
}

DECISION_TYPE_ALIASES = {
    "REVIEW_POST_DRAFT": "REVIEW_POST_DRAFT",
    "REVIEW_POST": "REVIEW_POST_DRAFT",
    "CLARIFY_REQUIREMENT": "CLARIFY_REQUIREMENT",
    "APPROVE_PROPOSAL": "APPROVE_PROPOSAL",
    "APPROVE_MATCH_CHANGE": "REVIEW_MATCH_CHANGE",
    "APPROVE_DISCLOSURE": "APPROVE_DISCLOSURE",
    "REVALIDATE_EXPIRED_OFFER": "REVALIDATE_EXPIRED_OFFER",
    "JOIN_SHARED_ROOM": "JOIN_SHARED_ROOM",
    "CONFIRM_MEMORY": "CONFIRM_MEMORY",
    "REVIEW_REPORT": "REVIEW_REPORT",
    "ACTIVATE_BACKUP": "ACTIVATE_BACKUP",
}


def _clean(document: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if not key.startswith("_")}


def _decision_type(decision: Mapping[str, Any]) -> str:
    raw = str(decision.get("type") or "").upper()
    if raw in DECISION_TYPE_ALIASES:
        return DECISION_TYPE_ALIASES[raw]
    if "PROPOSAL" in raw or "APPROVAL" in raw:
        return "APPROVE_PROPOSAL"
    if "MEMORY" in raw:
        return "CONFIRM_MEMORY"
    return raw or "CLARIFY_REQUIREMENT"


def _entity_route(decision: Mapping[str, Any]) -> str:
    if decision.get("match_id"):
        return f"/app/matches/{decision['match_id']}"
    if decision.get("room_id"):
        return f"/app/rooms/{decision['room_id']}"
    if decision.get("memory_id"):
        return f"/app/memory/{decision['memory_id']}"
    entity_ids = [str(item) for item in decision.get("entity_ids", [])]
    memory_id = next((item for item in entity_ids if item.startswith("memory_")), None)
    if memory_id:
        return f"/app/memory/{memory_id}"
    if decision.get("task_id"):
        tab_by_type = {
            "REVIEW_POST_DRAFT": "post",
            "APPROVE_PROPOSAL": "candidates",
            "ACTIVATE_BACKUP": "candidates",
        }
        tab = tab_by_type.get(_decision_type(decision), "overview")
        return f"/app/requests/{decision['task_id']}?tab={tab}"
    return "/app/agent"


def _decision_projection(decision: Mapping[str, Any]) -> dict[str, Any]:
    decision_type = _decision_type(decision)
    inline_types = {"APPROVE_PROPOSAL", "REVIEW_MATCH_CHANGE", "CONFIRM_MEMORY"}
    return {
        "decision_id": decision.get("decision_id"),
        "task_id": decision.get("task_id"),
        "type": decision_type,
        "status": decision.get("status") or "OPEN",
        "title": decision.get("title") or decision_type.replace("_", " ").title(),
        "summary": decision.get("summary")
        or "Open the authoritative entity to review.",
        "priority": decision.get("priority") or "NORMAL",
        "created_at": decision.get("created_at"),
        "expires_at": decision.get("expires_at"),
        "resolved_at": decision.get("resolved_at"),
        "entity_route": _entity_route(decision),
        "can_resolve_inline": decision_type in inline_types
        and not (
            decision_type == "CONFIRM_MEMORY"
            and len(decision.get("entity_ids", [])) > 1
        ),
        "required_confirmation": (
            f"APPROVE VERSION {int(decision.get('proposal_version', 1))}"
            if decision_type == "APPROVE_PROPOSAL"
            else f"APPROVE CHANGE VERSION {int(decision.get('version', 2))}"
            if decision_type == "REVIEW_MATCH_CHANGE"
            else None
        ),
    }


async def list_decision_inbox(
    store: Any, principal: AuthenticatedPrincipal
) -> dict[str, Any]:
    decisions = await store.query_documents(
        "decisions", filters=[("owner_uid", "EQUAL", principal.uid)]
    )
    items = [
        _decision_projection(item)
        for item in decisions
        if item.get("namespace") == PRODUCTION_NAMESPACE
    ]
    items.sort(
        key=lambda item: (
            item["status"] != "OPEN",
            str(item.get("created_at") or ""),
        )
    )
    return {
        "decisions": items,
        "open": [item for item in items if item["status"] == "OPEN"],
        "resolved": [item for item in items if item["status"] != "OPEN"],
        "open_count": sum(item["status"] == "OPEN" for item in items),
    }


async def resolve_decision(
    store: Any,
    principal: AuthenticatedPrincipal,
    *,
    decision_id: str,
    outcome: str,
    confirmation: str | None,
) -> dict[str, Any]:
    decision = await store.get("decisions", decision_id)
    if (
        decision is None
        or decision.get("namespace") != PRODUCTION_NAMESPACE
        or decision.get("owner_uid") != principal.uid
    ):
        raise LookupError("decision was not found")
    if decision.get("status") != "OPEN":
        return _decision_projection(decision)
    decision_type = _decision_type(decision)
    if outcome == "REJECT":
        clean = _clean(decision)
        clean.update(status="REJECTED", resolved_at=datetime.now(UTC))
        await store.upsert("decisions", decision_id, clean)
        change_id = str(decision.get("change_id") or "")
        if change_id:
            change = await store.get("match_change_proposals", change_id)
            if change is not None:
                clean_change = _clean(change)
                clean_change.update(status="REJECTED", rejected_at=datetime.now(UTC))
                await store.upsert("match_change_proposals", change_id, clean_change)
        return _decision_projection(clean)
    if decision_type == "REVIEW_MATCH_CHANGE":
        version = int(decision.get("version") or 2)
        await approve_match_change(
            store,
            principal,
            match_id=str(decision.get("match_id")),
            change_id=str(decision.get("change_id")),
            version=version,
            confirmation=confirmation or "",
        )
    elif decision_type == "APPROVE_PROPOSAL":
        version = int(decision.get("proposal_version") or 1)
        try:
            await approve_multi_user_proposal(
                store,
                principal,
                proposal_id=str(decision.get("proposal_id")),
                proposal_version=version,
                confirmation=confirmation or "",
            )
        except MultiUserCommitError as exc:
            raise ValueError(str(exc)) from exc
    elif decision_type == "CONFIRM_MEMORY":
        memory_ids = [
            str(item)
            for item in decision.get("entity_ids", [])
            if str(item).startswith("memory_")
        ]
        memory_id = str(
            decision.get("memory_id") or (memory_ids[0] if memory_ids else "")
        )
        await apply_memory_action(
            store,
            principal,
            memory_id=memory_id,
            action="CONFIRM",
            content=None,
            scope=None,
        )
    else:
        raise ValueError("this decision requires its authoritative workflow")
    refreshed = await store.get("decisions", decision_id)
    if refreshed is None:
        raise RuntimeError("resolved decision disappeared")
    return _decision_projection(refreshed)


def _notification_category(notification: Mapping[str, Any]) -> str:
    value = str(notification.get("type") or "").upper()
    if "DECISION" in value or "CLARIF" in value or "MEMORY" in value:
        return "DECISION_REQUIRED"
    if "CANDIDATE" in value or "RANK" in value or "SAVED_SEARCH" in value:
        return "CANDIDATE_CHANGE"
    if "MESSAGE" in value or "REPLIED" in value or "CONTACT_CARD" in value:
        return "AGENT_MESSAGE"
    if "PROPOSAL" in value or "OFFER" in value:
        return "PROPOSAL_UPDATE"
    if "MATCH" in value or "PLAN" in value:
        return "MATCH_UPDATE"
    if "COMMUNITY" in value:
        return "COMMUNITY_UPDATE"
    return "SYSTEM"


def _notification_route(notification: Mapping[str, Any]) -> str:
    entity_ids = [str(item) for item in notification.get("entity_ids", []) if item]
    for prefix, route in (
        ("intent_", "/app/posts/"),
        ("match_", "/app/matches/"),
        ("room_", "/app/rooms/"),
        ("task_", "/app/requests/"),
        ("memory_", "/app/memory/"),
        ("community_", "/app/communities/"),
    ):
        entity_id = next((item for item in entity_ids if item.startswith(prefix)), None)
        if entity_id:
            return f"{route}{entity_id}"
    return "/app/agent"


def _notification_projection(notification: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "notification_id": notification.get("notification_id"),
        "category": _notification_category(notification),
        "type": notification.get("type"),
        "title": notification.get("title"),
        "body": notification.get("body"),
        "status": notification.get("status") or "UNREAD",
        "entity_route": _notification_route(notification),
        "created_at": notification.get("created_at"),
    }


async def list_notifications(
    store: Any, principal: AuthenticatedPrincipal
) -> dict[str, Any]:
    notifications, settings = await asyncio.gather(
        store.query_documents(
            "notifications", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
        store.get("notification_settings", principal.uid),
    )
    items = [
        _notification_projection(item)
        for item in notifications
        if item.get("namespace") == PRODUCTION_NAMESPACE
    ]
    items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    categories = {
        category: [item for item in items if item["category"] == category]
        for category in (
            "DECISION_REQUIRED",
            "CANDIDATE_CHANGE",
            "AGENT_MESSAGE",
            "PROPOSAL_UPDATE",
            "MATCH_UPDATE",
            "COMMUNITY_UPDATE",
            "SYSTEM",
        )
    }
    return {
        "notifications": items,
        "categories": categories,
        "unread_count": sum(item["status"] == "UNREAD" for item in items),
        "settings": _clean(settings or {}),
    }


async def set_notification_state(
    store: Any,
    principal: AuthenticatedPrincipal,
    *,
    notification_id: str,
    state: str,
) -> dict[str, Any]:
    notification = await store.get("notifications", notification_id)
    if (
        notification is None
        or notification.get("owner_uid") != principal.uid
        or notification.get("namespace") != PRODUCTION_NAMESPACE
    ):
        raise LookupError("notification was not found")
    clean = _clean(notification)
    clean.update(status=state, updated_at=datetime.now(UTC))
    await store.upsert("notifications", notification_id, clean)
    return _notification_projection(clean)


async def mark_all_notifications_read(
    store: Any, principal: AuthenticatedPrincipal
) -> dict[str, Any]:
    notifications = await store.query_documents(
        "notifications", filters=[("owner_uid", "EQUAL", principal.uid)]
    )
    count = 0
    for notification in notifications:
        if notification.get("status") != "UNREAD":
            continue
        clean = _clean(notification)
        clean.update(status="READ", updated_at=datetime.now(UTC))
        await store.upsert("notifications", str(notification["notification_id"]), clean)
        count += 1
    return {"updated": count}


async def update_notification_settings(
    store: Any,
    principal: AuthenticatedPrincipal,
    *,
    values: Mapping[str, Any],
) -> dict[str, Any]:
    existing = await store.get("notification_settings", principal.uid) or {}
    clean = _clean(existing)
    clean.update(
        schema_version=SCHEMA_VERSION,
        namespace=PRODUCTION_NAMESPACE,
        owner_uid=principal.uid,
        **dict(values),
        updated_at=datetime.now(UTC),
    )
    if clean.get("browser_push_enabled") and not clean.get("browser_push_consent_at"):
        clean["browser_push_enabled"] = False
        clean["browser_push_status"] = "CONSENT_NOT_REGISTERED"
    await store.upsert("notification_settings", principal.uid, clean)
    return _clean(clean)


def _safe_action_levels(document: Mapping[str, Any]) -> dict[str, str]:
    stored = dict(document.get("action_levels") or {})
    levels = {
        **ACTION_DEFAULTS,
        **{str(key): str(value) for key, value in stored.items()},
    }
    levels["APPROVE_FINAL_COMMITMENT"] = "ASK_FIRST"
    return levels


async def get_autonomy_center(
    store: Any, principal: AuthenticatedPrincipal
) -> dict[str, Any]:
    config, overrides, activity = await asyncio.gather(
        store.get("user_autonomy_configs", principal.uid),
        store.query_documents(
            "autonomy_task_overrides", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
        store.query_documents(
            "autonomy_activity_events", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
    )
    return {
        "action_levels": _safe_action_levels(config or {}),
        "locked_actions": ["APPROVE_FINAL_COMMITMENT"],
        "task_overrides": [
            {
                "override_id": item.get("override_id"),
                "task_id": item.get("task_id"),
                "action_levels": dict(item.get("action_levels") or {}),
                "updated_at": item.get("updated_at"),
            }
            for item in overrides
        ],
        "activity": [
            {
                key: value
                for key, value in item.items()
                if key
                in {"activity_id", "action", "level", "task_id", "source", "created_at"}
            }
            for item in sorted(
                activity,
                key=lambda item: str(item.get("created_at") or ""),
                reverse=True,
            )[:50]
        ],
    }


async def update_autonomy_policy(
    store: Any,
    principal: AuthenticatedPrincipal,
    *,
    action_levels: Mapping[str, str],
    task_id: str | None,
) -> dict[str, Any]:
    allowed_actions = set(ACTION_DEFAULTS)
    invalid = set(action_levels) - allowed_actions
    if invalid:
        raise ValueError(f"unsupported autonomy action: {sorted(invalid)[0]}")
    if action_levels.get("APPROVE_FINAL_COMMITMENT") == "AUTOMATIC":
        raise ValueError("final commitment cannot become automatic")
    if task_id:
        task = await store.get("task_workspaces", task_id)
        if task is None or task.get("owner_uid") != principal.uid:
            raise LookupError("task was not found")
        override_id = stable_id("autonomy_override", principal.uid, task_id)
        existing = await store.get("autonomy_task_overrides", override_id) or {}
        clean = _clean(existing)
        clean.update(
            schema_version=SCHEMA_VERSION,
            namespace=PRODUCTION_NAMESPACE,
            override_id=override_id,
            owner_uid=principal.uid,
            task_id=task_id,
            action_levels={
                **dict(existing.get("action_levels") or {}),
                **dict(action_levels),
            },
            updated_at=datetime.now(UTC),
        )
        await store.upsert("autonomy_task_overrides", override_id, clean)
    else:
        existing = await store.get("user_autonomy_configs", principal.uid) or {}
        clean = _clean(existing)
        clean.update(
            schema_version=SCHEMA_VERSION,
            namespace=PRODUCTION_NAMESPACE,
            owner_uid=principal.uid,
            action_levels={
                **dict(existing.get("action_levels") or {}),
                **dict(action_levels),
            },
            updated_at=datetime.now(UTC),
        )
        clean["action_levels"]["APPROVE_FINAL_COMMITMENT"] = "ASK_FIRST"
        await store.upsert("user_autonomy_configs", principal.uid, clean)
    for action, level in action_levels.items():
        activity_id = f"autonomy_activity_{uuid4().hex}"
        await store.create(
            "autonomy_activity_events",
            activity_id,
            {
                "schema_version": SCHEMA_VERSION,
                "namespace": PRODUCTION_NAMESPACE,
                "activity_id": activity_id,
                "owner_uid": principal.uid,
                "action": action,
                "level": level,
                "task_id": task_id,
                "source": "OWNER_POLICY_CHANGE",
                "created_at": datetime.now(UTC),
            },
        )
    return await get_autonomy_center(store, principal)


async def autonomy_level_for(
    store: Any, *, owner_uid: str, action: str, task_id: str | None
) -> str:
    if action == "APPROVE_FINAL_COMMITMENT":
        return "ASK_FIRST"
    if task_id:
        override_id = stable_id("autonomy_override", owner_uid, task_id)
        override = await store.get("autonomy_task_overrides", override_id) or {}
        level = dict(override.get("action_levels") or {}).get(action)
        if level:
            return str(level)
    config = await store.get("user_autonomy_configs", owner_uid) or {}
    return _safe_action_levels(config).get(action, "ASK_FIRST")
