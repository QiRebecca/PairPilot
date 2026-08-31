"""Additive V1 community, notification, and Memory-authority services."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from pairpilot_orchestrator.auth.authorization import require_verified_email
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal

V1_SCHEMA_VERSION = 3
DEFAULT_COMMUNITY_ID = "community_icml_seoul_2026"
SUPPORTED_INTENT_TYPES = {
    "ROOM_SHARE",
    "MEAL_COMPANION",
    "COFFEE_CHAT",
    "EVENT_BUDDY",
    "HACKATHON_TEAMMATE",
}
LEGACY_INTENT_TYPE_ALIASES = {
    "conference_room_share": "ROOM_SHARE",
    "room_share": "ROOM_SHARE",
    "meal_companion": "MEAL_COMPANION",
    "coffee_chat": "COFFEE_CHAT",
    "event_buddy": "EVENT_BUDDY",
    "hackathon_teammate": "HACKATHON_TEAMMATE",
}


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode()).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _clean(document: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if not key.startswith("_")}


def normalize_intent_type(value: str) -> str:
    normalized = LEGACY_INTENT_TYPE_ALIASES.get(value, value.upper())
    if normalized not in SUPPORTED_INTENT_TYPES:
        raise ValueError("UNSUPPORTED_INTENT_TYPE")
    return normalized


def memory_is_confirmed(memory: Mapping[str, Any]) -> bool:
    status = str(memory.get("status") or memory.get("confirmation_status") or "")
    return status.upper() == "CONFIRMED" and memory.get("archived") is not True


async def ensure_v1_foundation(store: Any) -> None:
    """Create global public community records idempotently."""

    communities = [
        {
            "schema_version": V1_SCHEMA_VERSION,
            "namespace": "production",
            "community_id": DEFAULT_COMMUNITY_ID,
            "name": "ICML Seoul 2026",
            "description": (
                "Conference attendees coordinating rooms, meals, coffee chats, "
                "and local plans."
            ),
            "type": "CONFERENCE_EVENT",
            "location": "Seoul, South Korea",
            "start_time": datetime(2026, 7, 6, tzinfo=UTC),
            "end_time": datetime(2026, 7, 11, tzinfo=UTC),
            "visibility": "PUBLIC",
            "membership_policy": "PUBLIC_JOIN",
            "moderator_uids": [],
            "status": "ACTIVE",
            "created_at": datetime(2026, 8, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 8, 1, tzinfo=UTC),
        },
        {
            "schema_version": V1_SCHEMA_VERSION,
            "namespace": "production",
            "community_id": "community_hk_disney_buddies",
            "name": "Hong Kong Disneyland Buddies",
            "description": (
                "Find park companions for photos, rides, food, and shared planning."
            ),
            "type": "LOCAL_INTEREST",
            "location": "Hong Kong",
            "visibility": "PUBLIC",
            "membership_policy": "PUBLIC_JOIN",
            "moderator_uids": [],
            "status": "ACTIVE",
            "created_at": datetime(2026, 8, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 8, 1, tzinfo=UTC),
        },
        {
            "schema_version": V1_SCHEMA_VERSION,
            "namespace": "production",
            "community_id": "community_agent_builders",
            "name": "Agent Builders",
            "description": (
                "Meet collaborators building practical AI agents and "
                "agent-to-agent products."
            ),
            "type": "PROFESSIONAL_INTEREST",
            "location": "Global",
            "visibility": "PUBLIC",
            "membership_policy": "PUBLIC_JOIN",
            "moderator_uids": [],
            "status": "ACTIVE",
            "created_at": datetime(2026, 8, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 8, 1, tzinfo=UTC),
        },
        {
            "schema_version": V1_SCHEMA_VERSION,
            "namespace": "production",
            "community_id": "community_shanghai_weekend",
            "name": "Shanghai Weekend Plans",
            "description": (
                "Low-pressure meals, coffee chats, events, and weekend "
                "activities around Shanghai."
            ),
            "type": "LOCAL_INTEREST",
            "location": "Shanghai, China",
            "visibility": "PUBLIC",
            "membership_policy": "PUBLIC_JOIN",
            "moderator_uids": [],
            "status": "ACTIVE",
            "created_at": datetime(2026, 8, 1, tzinfo=UTC),
            "updated_at": datetime(2026, 8, 1, tzinfo=UTC),
        },
    ]
    for community in communities:
        await store.create(
            "communities", str(community["community_id"]), community
        )


async def join_community(
    store: Any,
    principal: AuthenticatedPrincipal,
    community_id: str,
    *,
    invite_token: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    require_verified_email(principal)
    await ensure_v1_foundation(store)
    community = await store.get("communities", community_id)
    if community is None or community.get("status") != "ACTIVE":
        raise LookupError("community was not found")
    if community.get("membership_policy") == "INVITE_REQUIRED" and not invite_token:
        raise PermissionError("COMMUNITY_INVITE_REQUIRED")
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    membership_id = _stable_id("membership", community_id, principal.uid)
    existing = await store.get("community_memberships", membership_id)
    membership = {
        "schema_version": V1_SCHEMA_VERSION,
        "namespace": "production",
        "membership_id": membership_id,
        "community_id": community_id,
        "owner_uid": principal.uid,
        "role": str(existing.get("role", "MEMBER")) if existing else "MEMBER",
        "status": "ACTIVE",
        "email_verification_evidence": True,
        "joined_at": existing.get("joined_at", timestamp) if existing else timestamp,
        "updated_at": timestamp,
    }
    await store.upsert("community_memberships", membership_id, membership)
    return _clean(membership)


async def leave_community(
    store: Any,
    principal: AuthenticatedPrincipal,
    community_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    membership_id = _stable_id("membership", community_id, principal.uid)
    existing = await store.get("community_memberships", membership_id)
    if existing is None or existing.get("owner_uid") != principal.uid:
        raise LookupError("community membership was not found")
    clean = _clean(existing)
    clean.update(status="LEFT", updated_at=now or datetime.now(UTC))
    await store.upsert("community_memberships", membership_id, clean)
    posts = await store.query_documents(
        "intent_posts", filters=[("owner_uid", "EQUAL", principal.uid)]
    )
    for post in posts:
        if post.get("community_id") != community_id or post.get("status") != "OPEN":
            continue
        paused = _clean(post)
        paused.update(status="PAUSED", updated_at=now or datetime.now(UTC))
        await store.upsert("intent_posts", str(post["intent_id"]), paused)
        await store.write_event(
            event_type="intent.paused.v1",
            run_id=str(post["task_id"]),
            producer=str(post["owner_agent_id"]),
            payload={
                "taskId": str(post["task_id"]),
                "intentId": str(post["intent_id"]),
                "reason": "COMMUNITY_LEFT",
            },
            idempotency_key=(f"community-left:{community_id}:{post['intent_id']}"),
        )
    return clean


async def active_community_ids(store: Any, owner_uid: str) -> set[str]:
    memberships = await store.query_documents(
        "community_memberships", filters=[("owner_uid", "EQUAL", owner_uid)]
    )
    return {
        str(item["community_id"])
        for item in memberships
        if item.get("status") == "ACTIVE"
    }


async def require_active_membership(
    store: Any, principal: AuthenticatedPrincipal, community_id: str
) -> None:
    if community_id not in await active_community_ids(store, principal.uid):
        raise PermissionError("COMMUNITY_MEMBERSHIP_REQUIRED")


async def list_communities_for_user(
    store: Any, principal: AuthenticatedPrincipal
) -> dict[str, list[dict[str, Any]]]:
    await ensure_v1_foundation(store)
    communities = await store.query_documents(
        "communities", filters=[("status", "EQUAL", "ACTIVE")]
    )
    memberships = await store.query_documents(
        "community_memberships", filters=[("owner_uid", "EQUAL", principal.uid)]
    )
    active = {
        str(item["community_id"]): _clean(item)
        for item in memberships
        if item.get("status") == "ACTIVE"
    }
    visible = [
        _clean(item)
        for item in communities
        if item.get("visibility") == "PUBLIC" or str(item.get("community_id")) in active
    ]
    return {"communities": visible, "memberships": list(active.values())}


async def update_memory_lifecycle(
    store: Any,
    principal: AuthenticatedPrincipal,
    memory_id: str,
    *,
    action: str,
    content: str | None = None,
    scope: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    memory = await store.get("memories", memory_id)
    if memory is None:
        raise LookupError("memory was not found")
    if memory.get("owner_uid") != principal.uid:
        raise PermissionError("memory is not owned by this user")
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    clean = _clean(memory)
    if action == "CONFIRM":
        clean.update(
            status="CONFIRMED",
            confirmation_status="CONFIRMED",
            last_confirmed_at=timestamp,
            archived=False,
        )
    elif action == "EDIT_AND_CONFIRM":
        if not content:
            raise ValueError("edited Memory content is required")
        clean.update(
            content=content,
            scope=scope or clean.get("scope", "GLOBAL"),
            status="CONFIRMED",
            confirmation_status="CONFIRMED",
            last_confirmed_at=timestamp,
            archived=False,
        )
    elif action == "REJECT":
        clean.update(status="REJECTED", confirmation_status="REJECTED", archived=True)
    elif action == "ARCHIVE":
        clean.update(status="ARCHIVED", confirmation_status="ARCHIVED", archived=True)
    elif action == "RESTRICT_SCOPE":
        if not scope:
            raise ValueError("restricted Memory scope is required")
        clean.update(scope=scope)
    elif action == "STOP_USING":
        clean.update(scope="DO_NOT_USE")
    elif action == "DELETE":
        clean.update(
            content="",
            status="ARCHIVED",
            confirmation_status="ARCHIVED",
            archived=True,
            deleted_at=timestamp,
        )
    else:
        raise ValueError("unsupported Memory action")
    clean["updated_at"] = timestamp
    await store.upsert("memories", memory_id, clean)
    await store.write_event(
        event_type="product.memory_lifecycle_changed.v1",
        run_id=memory_id,
        producer=principal.uid,
        payload={
            "memoryId": memory_id,
            "action": action,
            "status": clean.get("status"),
        },
        idempotency_key=f"memory:{memory_id}:{action}:{timestamp.isoformat()}",
        publish_immediately=False,
    )
    return clean


async def create_notification(
    store: Any,
    *,
    owner_uid: str,
    notification_type: str,
    title: str,
    body: str,
    entity_ids: list[str],
    idempotency_key: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    notification_id = _stable_id("notification", owner_uid, idempotency_key)
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    settings = await store.get("notification_settings", owner_uid)
    if settings is not None and settings.get("preference") == "NONE":
        return {
            "notification_id": notification_id,
            "owner_uid": owner_uid,
            "status": "SUPPRESSED_BY_USER",
        }
    document = {
        "schema_version": V1_SCHEMA_VERSION,
        "namespace": "production",
        "notification_id": notification_id,
        "owner_uid": owner_uid,
        "type": notification_type,
        "title": title,
        "body": body,
        "entity_ids": entity_ids,
        "status": "UNREAD",
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    await store.create("notifications", notification_id, document)
    existing = await store.get("notifications", notification_id)
    return _clean(existing or document)
