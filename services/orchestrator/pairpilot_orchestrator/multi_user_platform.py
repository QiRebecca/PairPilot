"""Authenticated, owner-scoped PairPilot public-beta product services."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Protocol, cast
from uuid import uuid4

from pairpilot_schemas import CreateUserTaskInput, OnboardingInput

from pairpilot_orchestrator.auth.authorization import (
    require_resource_owner,
    require_task_owner,
    require_verified_email,
)
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.infrastructure.google_cloud import encode_fields

SCHEMA_VERSION = 2
PRODUCTION_NAMESPACE = "production"
MAX_ACTIVE_TASKS_PER_USER = 3
MAX_NEW_CONTACTS_PER_TASK = 5


class MultiUserStore(Protocol):
    def document_name(self, collection: str, document_id: str) -> str: ...

    async def get(
        self, collection: str, document_id: str
    ) -> dict[str, Any] | None: ...

    async def query_documents(
        self,
        collection: str,
        *,
        filters: list[tuple[str, str, Any]],
        limit: int = 100,
    ) -> list[dict[str, Any]]: ...

    async def create(
        self, collection: str, document_id: str, data: Mapping[str, Any]
    ) -> bool: ...

    async def upsert(
        self, collection: str, document_id: str, data: Mapping[str, Any]
    ) -> dict[str, Any]: ...

    async def commit_writes(self, writes: list[dict[str, Any]]) -> dict[str, Any]: ...

    async def write_event(
        self,
        *,
        event_type: str,
        run_id: str,
        producer: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
        publish_immediately: bool = True,
    ) -> dict[str, Any]: ...


def stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("|".join(parts).encode()).hexdigest()[:24]
    return f"{prefix}_{digest}"


def agent_id_for_uid(uid: str) -> str:
    return stable_id("agent", uid)


def global_conversation_id_for_uid(uid: str) -> str:
    return stable_id("conversation_global", uid)


def _clean(document: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if not key.startswith("_")}


def _create_write(
    store: MultiUserStore,
    collection: str,
    document_id: str,
    data: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "update": {
            "name": store.document_name(collection, document_id),
            "fields": encode_fields(data),
        },
        "currentDocument": {"exists": False},
    }


def _update_write(
    store: MultiUserStore,
    collection: str,
    document_id: str,
    data: Mapping[str, Any],
    *,
    update_time: str,
) -> dict[str, Any]:
    return {
        "update": {
            "name": store.document_name(collection, document_id),
            "fields": encode_fields(data),
        },
        "currentDocument": {"updateTime": update_time},
    }


async def _ensure_document(
    store: MultiUserStore,
    collection: str,
    document_id: str,
    data: Mapping[str, Any],
) -> None:
    await store.create(collection, document_id, data)


async def provision_user(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create one complete, deterministic identity bundle atomically."""

    existing = await store.get("users", principal.uid)
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    agent_id = agent_id_for_uid(principal.uid)
    conversation_id = global_conversation_id_for_uid(principal.uid)
    documents: list[tuple[str, str, dict[str, Any]]] = [
        (
            "users",
            principal.uid,
            {
                "schema_version": SCHEMA_VERSION,
                "namespace": PRODUCTION_NAMESPACE,
                "uid": principal.uid,
                "display_name": "New member",
                "email": principal.email,
                "email_verified": principal.email_verified,
                "onboarding_status": "NOT_STARTED",
                "account_status": "ACTIVE",
                "personal_agent_id": agent_id,
                "timezone": "UTC",
                "adult_confirmed": False,
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        ),
        (
            "personal_agents",
            agent_id,
            {
                "schema_version": SCHEMA_VERSION,
                "namespace": PRODUCTION_NAMESPACE,
                "agent_id": agent_id,
                "owner_uid": principal.uid,
                "display_name": "Personal Agent",
                "public_card": {
                    "display_name": "Personal Agent",
                    "capabilities": [
                        "intent discovery",
                        "negotiation",
                        "coordination",
                    ],
                },
                "status": "ACTIVE",
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        ),
        (
            "conversations",
            conversation_id,
            {
                "schema_version": SCHEMA_VERSION,
                "namespace": PRODUCTION_NAMESPACE,
                "conversation_id": conversation_id,
                "owner_uid": principal.uid,
                "principal_agent_id": agent_id,
                "kind": "GLOBAL_PERSONAL_AGENT",
                "participant_uids": [principal.uid],
                "participant_agent_ids": [agent_id],
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        ),
        (
            "user_privacy_configs",
            principal.uid,
            {
                "schema_version": SCHEMA_VERSION,
                "namespace": PRODUCTION_NAMESPACE,
                "owner_uid": principal.uid,
                "public_profile_visible": False,
                "public_sharing_policy": "Ask before publishing.",
                "agent_sharing_policy": "Share only minimum task evidence.",
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        ),
        (
            "user_autonomy_configs",
            principal.uid,
            {
                "schema_version": SCHEMA_VERSION,
                "namespace": PRODUCTION_NAMESPACE,
                "owner_uid": principal.uid,
                "default_mode": "COPILOT",
                "always_ask_policy": (
                    "Publishing, identity disclosure, booking, payment, and "
                    "commitment require human approval."
                ),
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        ),
        (
            "usage_quotas",
            principal.uid,
            {
                "schema_version": SCHEMA_VERSION,
                "namespace": PRODUCTION_NAMESPACE,
                "owner_uid": principal.uid,
                "active_task_limit": MAX_ACTIVE_TASKS_PER_USER,
                "concurrent_negotiations_per_task": 2,
                "new_contacts_per_task": MAX_NEW_CONTACTS_PER_TASK,
                "daily_agent_turn_limit": 40,
                "agent_turns_today": 0,
                "quota_date": timestamp.date().isoformat(),
                "updated_at": timestamp,
            },
        ),
        (
            "user_namespaces",
            principal.uid,
            {
                "schema_version": SCHEMA_VERSION,
                "namespace": PRODUCTION_NAMESPACE,
                "owner_uid": principal.uid,
                "decision_namespace": stable_id("decisions", principal.uid),
                "memory_namespace": stable_id("memory", principal.uid),
                "relationship_namespace": stable_id("relationships", principal.uid),
                "created_at": timestamp,
            },
        ),
    ]
    if existing is None:
        try:
            await store.commit_writes(
                [
                    _create_write(store, collection, document_id, data)
                    for collection, document_id, data in documents
                ]
            )
        except Exception:
            existing = await store.get("users", principal.uid)
            if existing is None:
                raise
    if existing is not None:
        await asyncio.gather(
            *(
                _ensure_document(store, collection, document_id, data)
                for collection, document_id, data in documents[1:]
            )
        )
        clean = _clean(existing)
        if clean.get("email_verified") != principal.email_verified:
            clean["email_verified"] = principal.email_verified
            clean["updated_at"] = timestamp
            await store.upsert("users", principal.uid, clean)
    result = await store.get("users", principal.uid)
    if result is None:
        raise RuntimeError("provisioned user disappeared")
    return _clean(result)


async def complete_onboarding(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    body: OnboardingInput,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    profile_document = await store.get("users", principal.uid)
    if profile_document is None:
        await provision_user(store, principal, now=timestamp)
        profile_document = await store.get("users", principal.uid)
    if profile_document is None:
        raise RuntimeError("user profile is missing")
    profile = _clean(profile_document)
    profile.update(
        display_name=body.display_name,
        email=principal.email,
        email_verified=principal.email_verified,
        onboarding_status="COMPLETED",
        timezone=body.timezone,
        general_location=body.general_location,
        language=body.language,
        adult_confirmed=body.adult_confirmed,
        updated_at=timestamp,
    )
    agent_id = str(profile["personal_agent_id"])
    agent_document = await store.get("personal_agents", agent_id)
    if agent_document is None:
        raise RuntimeError("personal agent is missing")
    agent = _clean(agent_document)
    agent.update(
        display_name=f"{body.display_name} Agent",
        public_card={
            **dict(agent.get("public_card", {})),
            "display_name": f"{body.display_name} Agent",
        },
        updated_at=timestamp,
    )
    privacy_document = await store.get("user_privacy_configs", principal.uid)
    autonomy_document = await store.get("user_autonomy_configs", principal.uid)
    if privacy_document is None or autonomy_document is None:
        raise RuntimeError("default account policies are missing")
    privacy = _clean(privacy_document)
    privacy.update(
        public_profile_visible=body.public_profile_visible,
        public_sharing_policy=body.public_sharing_policy,
        agent_sharing_policy=body.agent_sharing_policy,
        updated_at=timestamp,
    )
    autonomy = _clean(autonomy_document)
    autonomy.update(
        default_mode=body.default_autonomy_mode,
        always_ask_policy=body.always_ask_policy,
        updated_at=timestamp,
    )
    await store.commit_writes(
        [
            _update_write(
                store,
                "users",
                principal.uid,
                profile,
                update_time=str(profile_document["_updateTime"]),
            ),
            _update_write(
                store,
                "personal_agents",
                agent_id,
                agent,
                update_time=str(agent_document["_updateTime"]),
            ),
            _update_write(
                store,
                "user_privacy_configs",
                principal.uid,
                privacy,
                update_time=str(privacy_document["_updateTime"]),
            ),
            _update_write(
                store,
                "user_autonomy_configs",
                principal.uid,
                autonomy,
                update_time=str(autonomy_document["_updateTime"]),
            ),
        ]
    )
    return profile


def _public_post_projection(post: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "schema_version",
        "intent_id",
        "owner_agent_id",
        "public_display_name",
        "task_type",
        "public_title",
        "public_constraints",
        "public_requirements",
        "status",
        "capacity",
        "capacity_remaining",
        "authorship",
        "published_at",
        "expires_at",
        "updated_at",
    }
    return {key: value for key, value in post.items() if key in allowed}


async def build_user_bootstrap(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
) -> dict[str, Any]:
    await provision_user(store, principal)
    agent_id = agent_id_for_uid(principal.uid)
    results = await asyncio.gather(
        store.get("users", principal.uid),
        store.get("personal_agents", agent_id),
        store.get("user_privacy_configs", principal.uid),
        store.get("user_autonomy_configs", principal.uid),
        store.get("usage_quotas", principal.uid),
        store.query_documents(
            "task_workspaces",
            filters=[("owner_uid", "EQUAL", principal.uid)],
        ),
        store.query_documents(
            "conversations", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
        store.query_documents(
            "conversation_messages",
            filters=[("owner_uid", "EQUAL", principal.uid)],
        ),
        store.query_documents(
            "decisions", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
        store.query_documents(
            "memories", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
        store.query_documents(
            "relationships", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
        store.query_documents(
            "coordination_rooms",
            filters=[("participant_uids", "ARRAY_CONTAINS", principal.uid)],
        ),
        store.query_documents(
            "matches",
            filters=[("participant_uids", "ARRAY_CONTAINS", principal.uid)],
        ),
        store.query_documents(
            "intent_posts", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
        store.query_documents(
            "intent_posts", filters=[("status", "EQUAL", "OPEN")]
        ),
        store.query_documents(
            "blocks", filters=[("blocker_uid", "EQUAL", principal.uid)]
        ),
        store.query_documents(
            "blocks", filters=[("blocked_uid", "EQUAL", principal.uid)]
        ),
    )
    profile = cast(dict[str, Any] | None, results[0])
    agent = cast(dict[str, Any] | None, results[1])
    privacy = cast(dict[str, Any] | None, results[2])
    autonomy = cast(dict[str, Any] | None, results[3])
    quota = cast(dict[str, Any] | None, results[4])
    tasks = cast(list[dict[str, Any]], results[5])
    conversations = cast(list[dict[str, Any]], results[6])
    messages = cast(list[dict[str, Any]], results[7])
    decisions = cast(list[dict[str, Any]], results[8])
    memories = cast(list[dict[str, Any]], results[9])
    relationships = cast(list[dict[str, Any]], results[10])
    rooms = cast(list[dict[str, Any]], results[11])
    matches = cast(list[dict[str, Any]], results[12])
    my_posts = cast(list[dict[str, Any]], results[13])
    open_posts = cast(list[dict[str, Any]], results[14])
    outgoing_blocks = cast(list[dict[str, Any]], results[15])
    incoming_blocks = cast(list[dict[str, Any]], results[16])
    blocked_uids = {
        str(item.get("blocked_uid")) for item in outgoing_blocks
    } | {str(item.get("blocker_uid")) for item in incoming_blocks}
    explore = [
        _public_post_projection(item)
        for item in open_posts
        if item.get("owner_uid") != principal.uid
        and item.get("owner_uid") not in blocked_uids
        and item.get("namespace") == PRODUCTION_NAMESPACE
    ]
    safe_rooms = []
    for room in rooms:
        clean_room = _clean(room)
        clean_room.pop("participant_uids", None)
        clean_room.pop("revoked_participant_uids", None)
        safe_rooms.append(clean_room)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "profile": _clean(profile or {}),
        "personalAgent": _clean(agent or {}),
        "privacy": _clean(privacy or {}),
        "autonomy": _clean(autonomy or {}),
        "quota": _clean(quota or {}),
        "tasks": [_clean(item) for item in tasks],
        "conversations": [_clean(item) for item in conversations],
        "conversationMessages": [_clean(item) for item in messages],
        "decisions": [_clean(item) for item in decisions],
        "memories": [_clean(item) for item in memories],
        "relationships": [_clean(item) for item in relationships],
        "rooms": safe_rooms,
        "matches": [
            {
                key: value
                for key, value in _clean(item).items()
                if key not in {"participant_uids"}
            }
            for item in matches
        ],
        "myPosts": [_public_post_projection(item) for item in my_posts],
        "explorePosts": explore,
    }


async def create_user_task(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    body: CreateUserTaskInput,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    await provision_user(store, principal)
    active_tasks = await store.query_documents(
        "task_workspaces", filters=[("owner_uid", "EQUAL", principal.uid)]
    )
    if (
        sum(
            item.get("status") not in {"COMPLETED", "CANCELLED"}
            for item in active_tasks
        )
        >= MAX_ACTIVE_TASKS_PER_USER
    ):
        raise ValueError("ACTIVE_TASK_QUOTA_EXCEEDED")
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    agent_id = agent_id_for_uid(principal.uid)
    task_id = f"task_{uuid4().hex}"
    intent_id = f"intent_{uuid4().hex}"
    conversation_id = stable_id("conversation_task", task_id)
    user_message_id = f"message_{uuid4().hex}"
    agent_message_id = f"message_{uuid4().hex}"
    review_decision_id = stable_id("decision_review", task_id)
    task = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "task_id": task_id,
        "owner_uid": principal.uid,
        "principal_agent_id": agent_id,
        "title": body.title,
        "task_type": body.task_type,
        "goal": body.goal,
        "status": "DRAFT",
        "conversation_id": conversation_id,
        "intent_id": intent_id,
        "decision_ids": [review_decision_id],
        "contact_count": 0,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    private_intent = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "intent_id": intent_id,
        "owner_uid": principal.uid,
        "owner_agent_id": agent_id,
        "task_id": task_id,
        "raw_user_goal": body.goal,
        "agent_only_constraints": {
            "maximum_additional_cost_usd": body.maximum_additional_cost_usd,
            "partial_date_overlap_allowed": body.partial_date_overlap_allowed,
        },
        "negotiation_boundaries": {
            "may_contact_verified_agents": False,
            "commitment_requires_human_approval": True,
        },
        "public_draft": {
            "event": body.event,
            "location": body.location,
            "date_start": body.date_start.isoformat(),
            "date_end": body.date_end.isoformat(),
            "public_requirements": body.public_requirements,
        },
        "provenance": {"source": "explicit_authenticated_user_input"},
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    conversation = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "conversation_id": conversation_id,
        "owner_uid": principal.uid,
        "principal_agent_id": agent_id,
        "kind": "TASK_USER_AGENT",
        "task_id": task_id,
        "participant_uids": [principal.uid],
        "participant_agent_ids": [agent_id],
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    user_message = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "message_id": user_message_id,
        "conversation_id": conversation_id,
        "task_id": task_id,
        "owner_uid": principal.uid,
        "role": "USER",
        "author_id": principal.uid,
        "content": body.goal,
        "visibility": "PRIVATE_USER_AGENT",
        "created_at": timestamp,
    }
    agent_message = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "message_id": agent_message_id,
        "conversation_id": conversation_id,
        "task_id": task_id,
        "owner_uid": principal.uid,
        "role": "PERSONAL_AGENT",
        "author_id": agent_id,
        "content": (
            "I created an isolated request and a private post draft. "
            "Review the public projection before I publish it."
        ),
        "visibility": "PRIVATE_USER_AGENT",
        "created_at": timestamp,
    }
    review_decision = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "decision_id": review_decision_id,
        "owner_uid": principal.uid,
        "task_id": task_id,
        "type": "REVIEW_POST_DRAFT",
        "status": "OPEN",
        "title": "Review what your Agent will publish",
        "summary": "Private and Agent-only constraints stay out of the public post.",
        "authoritative_entity_ids": [intent_id],
        "created_at": timestamp,
    }
    documents = [
        ("task_workspaces", task_id, task),
        ("intent_private_data", intent_id, private_intent),
        ("conversations", conversation_id, conversation),
        ("conversation_messages", user_message_id, user_message),
        ("conversation_messages", agent_message_id, agent_message),
        ("decisions", review_decision_id, review_decision),
    ]
    await store.commit_writes(
        [
            _create_write(store, collection, document_id, document)
            for collection, document_id, document in documents
        ]
    )
    return task


async def update_user_profile_verification(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
) -> None:
    profile = await store.get("users", principal.uid)
    if profile is None:
        return
    clean = _clean(profile)
    if clean.get("email_verified") == principal.email_verified:
        return
    clean.update(
        email_verified=principal.email_verified,
        updated_at=datetime.now(UTC),
    )
    await store.upsert("users", principal.uid, clean)


async def publish_user_post(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    task_id: str,
    public_title: str,
    public_summary: str,
    public_requirements: list[str],
    now: datetime | None = None,
) -> dict[str, Any]:
    require_verified_email(principal)
    task = await store.get("task_workspaces", task_id)
    if task is None:
        raise LookupError("task was not found")
    require_task_owner(principal, task)
    profile = await store.get("users", principal.uid)
    private_intent = await store.get("intent_private_data", str(task["intent_id"]))
    if profile is None or private_intent is None:
        raise RuntimeError("task ownership records are incomplete")
    require_resource_owner(principal, private_intent)
    if (
        profile.get("onboarding_status") != "COMPLETED"
        or profile.get("adult_confirmed") is not True
    ):
        raise PermissionError("ONBOARDING_REQUIRED")
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    intent_id = str(task["intent_id"])
    draft = dict(private_intent.get("public_draft", {}))
    post = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "intent_id": intent_id,
        "owner_uid": principal.uid,
        "owner_agent_id": str(task["principal_agent_id"]),
        "public_display_name": str(profile["display_name"]),
        "task_id": task_id,
        "task_type": str(task["task_type"]),
        "public_title": public_title,
        "public_summary": public_summary,
        "public_constraints": {
            "event": draft.get("event"),
            "location": draft.get("location"),
            "date_start": draft.get("date_start"),
            "date_end": draft.get("date_end"),
        },
        "public_requirements": public_requirements,
        "status": "OPEN",
        "capacity": 1,
        "capacity_remaining": 1,
        "authorship": {
            "drafted_by_agent_id": str(task["principal_agent_id"]),
            "approved_by_owner": True,
            "approved_at": timestamp,
        },
        "published_at": timestamp,
        "expires_at": timestamp.replace(year=timestamp.year + 1),
        "updated_at": timestamp,
    }
    task_clean = _clean(task)
    task_clean.update(status="SEARCHING", updated_at=timestamp)
    boundaries = dict(private_intent.get("negotiation_boundaries", {}))
    boundaries["may_contact_verified_agents"] = True
    private_clean = _clean(private_intent)
    private_clean.update(negotiation_boundaries=boundaries, updated_at=timestamp)
    existing_post = await store.get("intent_posts", intent_id)
    writes = []
    if existing_post is None:
        writes.append(_create_write(store, "intent_posts", intent_id, post))
    else:
        require_resource_owner(principal, existing_post)
        writes.append(
            _update_write(
                store,
                "intent_posts",
                intent_id,
                post,
                update_time=str(existing_post["_updateTime"]),
            )
        )
    writes.extend(
        [
            _update_write(
                store,
                "task_workspaces",
                task_id,
                task_clean,
                update_time=str(task["_updateTime"]),
            ),
            _update_write(
                store,
                "intent_private_data",
                intent_id,
                private_clean,
                update_time=str(private_intent["_updateTime"]),
            ),
        ]
    )
    await store.commit_writes(writes)
    for decision_id in task.get("decision_ids", []):
        decision = await store.get("decisions", str(decision_id))
        if decision and decision.get("type") == "REVIEW_POST_DRAFT":
            decision_clean = _clean(decision)
            decision_clean.update(status="RESOLVED", resolved_at=timestamp)
            await store.upsert("decisions", str(decision_id), decision_clean)
    await store.write_event(
        event_type="intent.published.v2",
        run_id=task_id,
        producer=str(task["principal_agent_id"]),
        payload={
            "schemaVersion": SCHEMA_VERSION,
            "namespace": PRODUCTION_NAMESPACE,
            "taskId": task_id,
            "intentId": intent_id,
            "ownerAgentId": str(task["principal_agent_id"]),
        },
        idempotency_key=f"v2:{intent_id}:published",
    )
    return _public_post_projection(post)


async def set_user_post_status(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    intent_id: str,
    status: str,
) -> dict[str, Any]:
    if status not in {"OPEN", "PAUSED", "CLOSED"}:
        raise ValueError("unsupported post status")
    if status == "OPEN":
        require_verified_email(principal)
    post = await store.get("intent_posts", intent_id)
    if post is None:
        raise LookupError("post was not found")
    require_resource_owner(principal, post)
    clean = _clean(post)
    clean.update(status=status, updated_at=datetime.now(UTC))
    if status == "CLOSED":
        clean["closed_to_new_contacts"] = True
    await store.upsert("intent_posts", intent_id, clean)
    return _public_post_projection(clean)


def effect_contract_hash(contract: Mapping[str, Any]) -> str:
    serialized = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode()).hexdigest()
