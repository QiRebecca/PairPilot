"""Authenticated, owner-scoped PairPilot public-beta product services."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, Protocol, cast
from uuid import uuid4

from pairpilot_schemas import (
    CreateUserTaskInput,
    IntentPostState,
    OnboardingInput,
    UpdateAccountSettingsInput,
    validate_intent_post_transition,
)

from pairpilot_orchestrator.auth.authorization import (
    require_resource_owner,
    require_room_participant,
    require_task_owner,
    require_verified_email,
)
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.infrastructure.google_cloud import encode_fields
from pairpilot_orchestrator.policies.privacy import OutboundPrivacyGuard
from pairpilot_orchestrator.v1_foundation import (
    DEFAULT_COMMUNITY_ID,
    active_community_ids,
    ensure_v1_foundation,
    join_community,
    list_communities_for_user,
    normalize_intent_type,
    require_active_membership,
)

SCHEMA_VERSION = 3
PRODUCTION_NAMESPACE = "production"
MAX_ACTIVE_TASKS_PER_USER = 3
MAX_NEW_CONTACTS_PER_TASK = 5


class MultiUserStore(Protocol):
    def document_name(self, collection: str, document_id: str) -> str: ...

    async def get(self, collection: str, document_id: str) -> dict[str, Any] | None: ...

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
    return f"user:{uid}:global"


def task_conversation_id_for_uid(uid: str, task_id: str) -> str:
    return f"user:{uid}:task:{task_id}"


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

    await ensure_v1_foundation(store)
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
                "admin": principal.admin,
                "personal_agent_id": agent_id,
                "timezone": "UTC",
                "adult_confirmed": False,
                "community_ids": [],
                "notification_preference": "IN_APP",
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
                "action_levels": {
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
                },
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
        (
            "notification_settings",
            principal.uid,
            {
                "schema_version": SCHEMA_VERSION,
                "namespace": PRODUCTION_NAMESPACE,
                "owner_uid": principal.uid,
                "preference": "IN_APP",
                "in_app_enabled": True,
                "email_enabled": False,
                "meaningful_events_only": True,
                "created_at": timestamp,
                "updated_at": timestamp,
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
        if (
            clean.get("email_verified") != principal.email_verified
            or clean.get("admin") != principal.admin
        ):
            clean["email_verified"] = principal.email_verified
            clean["admin"] = principal.admin
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
        community_ids=body.community_ids,
        notification_preference=body.notification_preference,
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
        default_public_visibility=body.default_public_visibility,
        default_agent_visibility=body.default_agent_visibility,
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
    if principal.email_verified:
        for community_id in body.community_ids:
            await join_community(store, principal, community_id, now=timestamp)
    notification_settings = await store.get("notification_settings", principal.uid)
    if notification_settings is not None:
        notification_clean = _clean(notification_settings)
        notification_clean.update(
            preference=body.notification_preference,
            in_app_enabled=body.notification_preference != "NONE",
            email_enabled=body.notification_preference == "IN_APP_AND_EMAIL",
            updated_at=timestamp,
        )
        await store.upsert("notification_settings", principal.uid, notification_clean)
    return profile


def _public_post_projection(post: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "schema_version",
        "intent_id",
        "owner_agent_id",
        "community_id",
        "public_display_name",
        "task_type",
        "public_title",
        "public_summary",
        "public_constraints",
        "public_requirements",
        "status",
        "capacity",
        "capacity_remaining",
        "authorship",
        "human_approval_status",
        "published_at",
        "expires_at",
        "updated_at",
    }
    projection = {key: value for key, value in post.items() if key in allowed}
    projection.setdefault("community_id", DEFAULT_COMMUNITY_ID)
    projection.setdefault("human_approval_status", "APPROVED")
    return projection


async def build_user_bootstrap(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
) -> dict[str, Any]:
    provisioned_profile = await provision_user(store, principal)
    if (
        principal.email_verified
        and provisioned_profile.get("onboarding_status") == "COMPLETED"
        and not await active_community_ids(store, principal.uid)
    ):
        await join_community(store, principal, DEFAULT_COMMUNITY_ID)
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
        store.query_documents("intent_posts", filters=[("status", "EQUAL", "OPEN")]),
        store.query_documents(
            "blocks", filters=[("blocker_uid", "EQUAL", principal.uid)]
        ),
        store.query_documents(
            "blocks", filters=[("blocked_uid", "EQUAL", principal.uid)]
        ),
        store.query_documents(
            "presentation_directives",
            filters=[("owner_uid", "EQUAL", principal.uid)],
        ),
        store.query_documents(
            "intent_private_data",
            filters=[("owner_uid", "EQUAL", principal.uid)],
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
    presentation_directives = cast(list[dict[str, Any]], results[17])
    private_intents = cast(list[dict[str, Any]], results[18])
    (
        community_payload,
        notifications,
        candidate_assessments,
        rank_events,
        contact_cards,
        outcomes,
    ) = await asyncio.gather(
        list_communities_for_user(store, principal),
        store.query_documents(
            "notifications", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
        store.query_documents(
            "candidate_assessments",
            filters=[("owner_uid", "EQUAL", principal.uid)],
        ),
        store.query_documents(
            "candidate_rank_events",
            filters=[("owner_uid", "EQUAL", principal.uid)],
        ),
        store.query_documents(
            "contact_cards", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
        store.query_documents(
            "outcomes", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
    )
    member_community_ids = {
        str(item["community_id"])
        for item in community_payload["memberships"]
        if item.get("status") == "ACTIVE"
    }
    blocked_uids = {str(item.get("blocked_uid")) for item in outgoing_blocks} | {
        str(item.get("blocker_uid")) for item in incoming_blocks
    }
    explore = [
        _public_post_projection(item)
        for item in open_posts
        if item.get("owner_uid") != principal.uid
        and item.get("owner_uid") not in blocked_uids
        and item.get("namespace") == PRODUCTION_NAMESPACE
        and str(item.get("community_id", DEFAULT_COMMUNITY_ID)) in member_community_ids
    ]
    safe_rooms = []
    for room in rooms:
        clean_room = _clean(room)
        clean_room.pop("participant_uids", None)
        clean_room.pop("revoked_participant_uids", None)
        safe_rooms.append(clean_room)
    canonical_global_conversation_id = global_conversation_id_for_uid(principal.uid)
    canonical_conversations = [
        item
        for item in conversations
        if item.get("kind") != "GLOBAL_PERSONAL_AGENT"
        or item.get("conversation_id") == canonical_global_conversation_id
    ]
    return {
        "schemaVersion": SCHEMA_VERSION,
        "profile": _clean(profile or {}),
        "personalAgent": _clean(agent or {}),
        "privacy": _clean(privacy or {}),
        "autonomy": _clean(autonomy or {}),
        "quota": _clean(quota or {}),
        "tasks": [
            {
                **_clean(item),
                "community_id": item.get("community_id", DEFAULT_COMMUNITY_ID),
                "agent_public_draft": next(
                    (
                        dict(private.get("public_draft", {}))
                        for private in private_intents
                        if private.get("intent_id") == item.get("intent_id")
                    ),
                    {},
                ),
            }
            for item in tasks
        ],
        "conversations": [_clean(item) for item in canonical_conversations],
        "conversationMessages": [_clean(item) for item in messages],
        "presentationDirectives": [_clean(item) for item in presentation_directives],
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
        "myPosts": [
            {
                **_public_post_projection(item),
                # Owner-only linkage for the authoritative publication state in
                # its private request workspace. Explore projections omit it.
                "task_id": item.get("task_id"),
            }
            for item in my_posts
        ],
        "explorePosts": explore,
        "communities": community_payload["communities"],
        "communityMemberships": community_payload["memberships"],
        "notifications": [_clean(item) for item in notifications],
        "candidateAssessments": [_clean(item) for item in candidate_assessments],
        "candidateRankEvents": [_clean(item) for item in rank_events],
        "contactCards": [_clean(item) for item in contact_cards],
        "outcomes": [_clean(item) for item in outcomes],
    }


async def create_user_task(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    body: CreateUserTaskInput,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    await provision_user(store, principal)
    if principal.email_verified:
        await require_active_membership(store, principal, body.community_id)
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
    conversation_id = task_conversation_id_for_uid(principal.uid, task_id)
    user_message_id = f"message_{uuid4().hex}"
    review_decision_id = stable_id("decision_review", task_id)
    task = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "task_id": task_id,
        "owner_uid": principal.uid,
        "principal_agent_id": agent_id,
        "title": body.title,
        "task_type": normalize_intent_type(body.task_type),
        "community_id": body.community_id,
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
        "community_id": body.community_id,
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
        "community_id": body.community_id,
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
        "message_classification": "MANUALLY_ENTERED_USER_CONTENT",
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
        ("decisions", review_decision_id, review_decision),
    ]
    await store.commit_writes(
        [
            _create_write(store, collection, document_id, document)
            for collection, document_id, document in documents
        ]
    )
    await store.write_event(
        event_type="product.task_created_and_post_drafted.v1",
        run_id=task_id,
        producer=agent_id,
        payload={
            "taskId": task_id,
            "intentId": intent_id,
            "communityId": body.community_id,
            "taskType": str(task["task_type"]),
        },
        idempotency_key=f"product:{task_id}:created",
        publish_immediately=False,
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
    community_id = str(task.get("community_id", DEFAULT_COMMUNITY_ID))
    await require_active_membership(store, principal, community_id)
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
    clean_title = public_title.strip()
    if not clean_title:
        raise ValueError("public title is required")
    clean_summary = public_summary.strip() or clean_title
    clean_requirements = [item.strip() for item in public_requirements if item.strip()]
    OutboundPrivacyGuard().validate(
        natural_language="\n".join([clean_title, clean_summary, *clean_requirements]),
        references=[],
    )
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
        "community_id": community_id,
        "task_type": normalize_intent_type(str(task["task_type"])),
        "public_title": clean_title,
        "public_summary": clean_summary,
        "public_constraints": {
            "event": draft.get("event"),
            "location": draft.get("location"),
            "date_start": draft.get("date_start"),
            "date_end": draft.get("date_end"),
        },
        "public_requirements": clean_requirements,
        "status": "OPEN",
        "capacity": 1,
        "capacity_remaining": 1,
        "authorship": {
            "drafted_by_agent_id": str(task["principal_agent_id"]),
            "approved_by_owner": True,
            "approved_at": timestamp,
        },
        "human_approval_status": "APPROVED",
        "published_at": timestamp,
        "expires_at": timestamp + timedelta(days=365),
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
        current_state = IntentPostState(str(existing_post.get("status", "")))
        validate_intent_post_transition(current_state, IntentPostState.OPEN)
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


async def save_user_post_draft(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    task_id: str,
    public_title: str,
    public_summary: str,
    public_requirements: list[str],
) -> dict[str, Any]:
    """Persist editable public fields without publishing or changing task state."""

    task = await store.get("task_workspaces", task_id)
    if task is None:
        raise LookupError("task was not found")
    require_task_owner(principal, task)
    intent_id = str(task["intent_id"])
    private_intent = await store.get("intent_private_data", intent_id)
    if private_intent is None:
        raise LookupError("private intent was not found")
    require_resource_owner(principal, private_intent)
    clean = _clean(private_intent)
    draft = dict(clean.get("public_draft", {}))
    draft.update(
        public_title=public_title.strip(),
        public_summary=public_summary.strip(),
        public_requirements=[
            item.strip() for item in public_requirements if item.strip()
        ],
    )
    clean.update(public_draft=draft, updated_at=datetime.now(UTC))
    await store.upsert("intent_private_data", intent_id, clean)
    return draft


async def set_user_post_status(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    intent_id: str,
    status: str,
) -> dict[str, Any]:
    if status not in {
        IntentPostState.OPEN.value,
        IntentPostState.PAUSED.value,
        IntentPostState.CLOSED.value,
    }:
        raise ValueError("unsupported post status")
    target_state = IntentPostState(status)
    if target_state == IntentPostState.OPEN:
        require_verified_email(principal)
    post = await store.get("intent_posts", intent_id)
    if post is None:
        raise LookupError("post was not found")
    require_resource_owner(principal, post)
    current_state = IntentPostState(str(post.get("status", "")))
    validate_intent_post_transition(current_state, target_state)
    clean = _clean(post)
    clean.update(status=target_state.value, updated_at=datetime.now(UTC))
    if target_state == IntentPostState.CLOSED:
        clean["closed_to_new_contacts"] = True
    await store.upsert("intent_posts", intent_id, clean)
    await store.write_event(
        event_type=f"intent.{status.lower()}.v1",
        run_id=str(clean["task_id"]),
        producer=str(clean["owner_agent_id"]),
        payload={
            "schemaVersion": SCHEMA_VERSION,
            "namespace": PRODUCTION_NAMESPACE,
            "taskId": str(clean["task_id"]),
            "intentId": intent_id,
            "status": status,
        },
        idempotency_key=(
            f"v1:{intent_id}:status:{status}:{clean['updated_at'].isoformat()}"
        ),
    )
    return _public_post_projection(clean)


def effect_contract_hash(contract: Mapping[str, Any]) -> str:
    def encode(value: object) -> str:
        if isinstance(value, datetime):
            return value.astimezone(UTC).isoformat()
        raise TypeError(f"unsupported effect-contract value: {type(value)!r}")

    serialized = json.dumps(
        contract,
        sort_keys=True,
        separators=(",", ":"),
        default=encode,
    )
    return sha256(serialized.encode()).hexdigest()


async def get_user_room(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    room_id: str,
) -> dict[str, Any]:
    room = await store.get("coordination_rooms", room_id)
    if room is None or room.get("namespace") != PRODUCTION_NAMESPACE:
        raise LookupError("room was not found")
    require_room_participant(principal, room)
    messages = await store.query_documents(
        "room_messages", filters=[("room_id", "EQUAL", room_id)]
    )
    safe_room = _clean(room)
    safe_room.pop("participant_uids", None)
    safe_room.pop("revoked_participant_uids", None)
    safe_messages = []
    for message in messages:
        clean_message = _clean(message)
        clean_message.pop("principal_owner_uid_internal", None)
        safe_messages.append(clean_message)
    return {"room": safe_room, "messages": safe_messages}


async def send_user_room_message(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    room_id: str,
    content: str,
    authorship: str,
    idempotency_key: str,
) -> dict[str, Any]:
    require_verified_email(principal)
    room = await store.get("coordination_rooms", room_id)
    if room is None or room.get("namespace") != PRODUCTION_NAMESPACE:
        raise LookupError("room was not found")
    require_room_participant(principal, room)
    if (
        room.get("room_type") != "SHARED_COORDINATION_ROOM"
        or room.get("human_participation_available") is not True
    ):
        raise PermissionError("SHARED_ROOM_NOT_UNLOCKED")
    OutboundPrivacyGuard().validate(natural_language=content, references=[])
    message_id = stable_id("room_message", room_id, principal.uid, idempotency_key)
    message = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "message_id": message_id,
        "room_id": room_id,
        "speaker_id": principal.uid,
        "speaker_type": "HUMAN",
        "authorship": authorship,
        "visibility": "SHARED_ROOM",
        "content": content,
        "provenance": {"source": "authenticated_room_member"},
        "created_at": datetime.now(UTC),
    }
    created = await store.create("room_messages", message_id, message)
    if not created:
        existing = await store.get("room_messages", message_id)
        if existing is None:
            raise RuntimeError("idempotent room message disappeared")
        return _clean(existing)
    return message


async def block_agent_owner(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    target_agent_id: str,
    reason: str | None,
) -> dict[str, Any]:
    target_agent = await store.get("personal_agents", target_agent_id)
    if target_agent is None or target_agent.get("namespace") != PRODUCTION_NAMESPACE:
        raise LookupError("target was not found")
    blocked_uid = str(target_agent.get("owner_uid", ""))
    if not blocked_uid or blocked_uid == principal.uid:
        raise ValueError("invalid block target")
    block_id = stable_id("block", principal.uid, blocked_uid)
    timestamp = datetime.now(UTC)
    block = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "block_id": block_id,
        "blocker_uid": principal.uid,
        "blocked_uid": blocked_uid,
        "blocked_agent_id": target_agent_id,
        "reason": reason,
        "status": "ACTIVE",
        "created_at": timestamp,
    }
    await store.create("blocks", block_id, block)
    proposals = await store.query_documents(
        "proposals",
        filters=[("participant_uids", "ARRAY_CONTAINS", principal.uid)],
    )
    for proposal in proposals:
        if (
            blocked_uid not in proposal.get("participant_uids", [])
            or proposal.get("status") != "AWAITING_HUMANS"
        ):
            continue
        proposal_clean = _clean(proposal)
        proposal_clean.update(status="CANCELLED_BY_BLOCK", updated_at=timestamp)
        await store.upsert("proposals", str(proposal["proposal_id"]), proposal_clean)
        hold_id = stable_id(
            "hold", str(proposal["proposal_id"]), str(proposal["version"])
        )
        hold = await store.get("holds", hold_id)
        if hold is not None and hold.get("active") is True:
            hold_clean = _clean(hold)
            hold_clean.update(
                active=False,
                status="RELEASED",
                release_reason="participant_blocked",
                released_at=timestamp,
            )
            await store.upsert("holds", hold_id, hold_clean)
        room = await store.get("coordination_rooms", str(proposal["room_id"]))
        if room is not None:
            room_clean = _clean(room)
            room_clean.update(
                status="CLOSED",
                human_participation_available=False,
                updated_at=timestamp,
            )
            await store.upsert(
                "coordination_rooms", str(proposal["room_id"]), room_clean
            )
    rooms = await store.query_documents(
        "coordination_rooms",
        filters=[("participant_uids", "ARRAY_CONTAINS", principal.uid)],
    )
    for room in rooms:
        if blocked_uid not in room.get("participant_uids", []):
            continue
        room_clean = _clean(room)
        room_clean.update(
            status="CLOSED_BY_BLOCK",
            human_participation_available=False,
            updated_at=timestamp,
        )
        await store.upsert("coordination_rooms", str(room["room_id"]), room_clean)
        cards = await store.query_documents(
            "contact_cards", filters=[("room_id", "EQUAL", room["room_id"])]
        )
        for card in cards:
            card_clean = _clean(card)
            card_clean.update(
                fields={}, status="REVOKED_BY_BLOCK", updated_at=timestamp
            )
            await store.upsert(
                "contact_cards", str(card["contact_card_id"]), card_clean
            )
    assessments = await store.query_documents(
        "candidate_assessments",
        filters=[("owner_uid", "EQUAL", principal.uid)],
    )
    for assessment in assessments:
        if assessment.get("candidate_agent_id") != target_agent_id:
            continue
        clean_assessment = _clean(assessment)
        clean_assessment.update(
            state="WITHDRAWN", last_material_change_at=timestamp, updated_at=timestamp
        )
        await store.upsert(
            "candidate_assessments",
            str(clean_assessment["assessment_id"]),
            clean_assessment,
        )
    return {"block_id": block_id, "status": "ACTIVE"}


async def create_user_report(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    target_type: str,
    target_id: str,
    category: str,
    details: str,
) -> dict[str, Any]:
    target: Mapping[str, Any] | None = None
    target_owner_uid: str | None = None
    community_id: str | None = None
    if target_type == "POST":
        target = await store.get("intent_posts", target_id)
        if target is not None:
            target_owner_uid = str(target.get("owner_uid") or "") or None
            community_id = str(target.get("community_id") or "") or None
    elif target_type == "MESSAGE":
        target = await store.get("room_messages", target_id)
        if target is not None:
            target_owner_uid = str(target.get("speaker_id") or "") or None
            room_id = str(target.get("room_id") or "")
            room = await store.get("coordination_rooms", room_id) if room_id else None
            if room is not None:
                community_id = str(room.get("community_id") or "") or None
    elif target_type == "USER":
        target = await store.get("personal_agents", target_id)
        if target is not None:
            target_owner_uid = str(target.get("owner_uid") or "") or None
    report_id = f"report_{uuid4().hex}"
    report = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "report_id": report_id,
        "reporter_uid": principal.uid,
        "target_type": target_type,
        "target_id": target_id,
        "target_owner_uid": target_owner_uid,
        "community_id": community_id,
        "category": category,
        "details": details,
        "status": "OPEN",
        "created_at": datetime.now(UTC),
    }
    await store.create("reports", report_id, report)
    await store.write_event(
        event_type="safety.report.created.v2",
        run_id=report_id,
        producer=principal.uid,
        payload={
            "reportId": report_id,
            "targetType": target_type,
            "category": category,
        },
        idempotency_key=f"v2:{report_id}:created",
    )
    return {"report_id": report_id, "status": "OPEN"}


async def update_account_settings(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    body: UpdateAccountSettingsInput,
) -> dict[str, Any]:
    profile, privacy, autonomy, notification_settings = await asyncio.gather(
        store.get("users", principal.uid),
        store.get("user_privacy_configs", principal.uid),
        store.get("user_autonomy_configs", principal.uid),
        store.get("notification_settings", principal.uid),
    )
    if profile is None or privacy is None or autonomy is None:
        raise LookupError("account settings were not found")
    timestamp = datetime.now(UTC)
    profile_clean = _clean(profile)
    profile_clean.update(display_name=body.display_name, updated_at=timestamp)
    privacy_clean = _clean(privacy)
    privacy_clean.update(
        public_sharing_policy=body.public_sharing_policy,
        agent_sharing_policy=body.agent_sharing_policy,
        updated_at=timestamp,
    )
    autonomy_clean = _clean(autonomy)
    autonomy_clean.update(
        default_mode=body.default_autonomy_mode,
        updated_at=timestamp,
    )
    writes = [
        _update_write(
            store,
            "users",
            principal.uid,
            profile_clean,
            update_time=str(profile["_updateTime"]),
        ),
        _update_write(
            store,
            "user_privacy_configs",
            principal.uid,
            privacy_clean,
            update_time=str(privacy["_updateTime"]),
        ),
        _update_write(
            store,
            "user_autonomy_configs",
            principal.uid,
            autonomy_clean,
            update_time=str(autonomy["_updateTime"]),
        ),
    ]
    notification_clean = _clean(notification_settings or {})
    if body.notification_preference is not None and notification_settings is not None:
        notification_clean.update(
            preference=body.notification_preference,
            in_app_enabled=body.notification_preference != "NONE",
            email_enabled=body.notification_preference == "IN_APP_AND_EMAIL",
            updated_at=timestamp,
        )
        writes.append(
            _update_write(
                store,
                "notification_settings",
                principal.uid,
                notification_clean,
                update_time=str(notification_settings["_updateTime"]),
            )
        )
        profile_clean["notification_preference"] = body.notification_preference
        writes[0] = _update_write(
            store,
            "users",
            principal.uid,
            profile_clean,
            update_time=str(profile["_updateTime"]),
        )
    await store.commit_writes(writes)
    return {
        "profile": profile_clean,
        "privacy": privacy_clean,
        "autonomy": autonomy_clean,
        "notificationSettings": notification_clean,
    }


async def export_account_data(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
) -> dict[str, Any]:
    """Return only the authenticated owner's portable private projection."""

    bootstrap = await build_user_bootstrap(store, principal)
    private_intents = await store.query_documents(
        "intent_private_data", filters=[("owner_uid", "EQUAL", principal.uid)]
    )
    reports = await store.query_documents(
        "reports", filters=[("reporter_uid", "EQUAL", principal.uid)]
    )
    bootstrap["privateIntents"] = [_clean(item) for item in private_intents]
    bootstrap["reportsFiled"] = [_clean(item) for item in reports]
    bootstrap["exportedAt"] = datetime.now(UTC)
    bootstrap["exportFormat"] = "pairpilot-account-v2"
    return bootstrap


async def leave_user_room(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    room_id: str,
) -> dict[str, Any]:
    room = await store.get("coordination_rooms", room_id)
    if room is None or room.get("namespace") != PRODUCTION_NAMESPACE:
        raise LookupError("room was not found")
    require_room_participant(principal, room)
    clean = _clean(room)
    revoked = {str(item) for item in clean.get("revoked_participant_uids", [])}
    revoked.add(principal.uid)
    clean.update(
        revoked_participant_uids=sorted(revoked),
        updated_at=datetime.now(UTC),
    )
    await store.upsert("coordination_rooms", room_id, clean)
    participant_id = stable_id("room_participant", room_id, principal.uid)
    membership = await store.get("room_participants", participant_id)
    if membership is not None:
        member_clean = _clean(membership)
        member_clean.update(status="REVOKED", revoked_at=datetime.now(UTC))
        await store.upsert("room_participants", participant_id, member_clean)
    return {"room_id": room_id, "status": "LEFT"}


async def schedule_account_deletion(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
) -> dict[str, Any]:
    """Remove the account from social activity before deferred erasure."""

    profile = await store.get("users", principal.uid)
    if profile is None:
        raise LookupError("account was not found")
    timestamp = datetime.now(UTC)
    posts, tasks, proposals, rooms = await asyncio.gather(
        store.query_documents(
            "intent_posts", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
        store.query_documents(
            "task_workspaces", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
        store.query_documents(
            "proposals",
            filters=[("participant_uids", "ARRAY_CONTAINS", principal.uid)],
        ),
        store.query_documents(
            "coordination_rooms",
            filters=[("participant_uids", "ARRAY_CONTAINS", principal.uid)],
        ),
    )
    for post in posts:
        clean = _clean(post)
        clean.update(
            status="CLOSED",
            closed_to_new_contacts=True,
            closed_reason="account_deletion",
            updated_at=timestamp,
        )
        await store.upsert("intent_posts", str(post["intent_id"]), clean)
    for task in tasks:
        if task.get("status") not in {"COMPLETED", "CANCELLED"}:
            clean = _clean(task)
            clean.update(status="CANCELLED", updated_at=timestamp)
            await store.upsert("task_workspaces", str(task["task_id"]), clean)
    for proposal in proposals:
        if proposal.get("status") == "AWAITING_HUMANS":
            clean = _clean(proposal)
            clean.update(status="CANCELLED_ACCOUNT_DELETION", updated_at=timestamp)
            await store.upsert("proposals", str(proposal["proposal_id"]), clean)
            hold_id = stable_id(
                "hold", str(proposal["proposal_id"]), str(proposal["version"])
            )
            hold = await store.get("holds", hold_id)
            if hold is not None and hold.get("active") is True:
                hold_clean = _clean(hold)
                hold_clean.update(
                    active=False,
                    status="RELEASED",
                    release_reason="account_deletion",
                    released_at=timestamp,
                )
                await store.upsert("holds", hold_id, hold_clean)
    for room in rooms:
        clean = _clean(room)
        revoked = {str(item) for item in clean.get("revoked_participant_uids", [])}
        revoked.add(principal.uid)
        clean.update(revoked_participant_uids=sorted(revoked), updated_at=timestamp)
        await store.upsert("coordination_rooms", str(room["room_id"]), clean)
    profile_clean = _clean(profile)
    profile_clean.update(
        account_status="DELETION_PENDING",
        deletion_requested_at=timestamp,
        discovery_enabled=False,
        updated_at=timestamp,
    )
    await store.upsert("users", principal.uid, profile_clean)
    request_id = stable_id("deletion_request", principal.uid)
    await store.create(
        "account_deletion_requests",
        request_id,
        {
            "schema_version": SCHEMA_VERSION,
            "namespace": PRODUCTION_NAMESPACE,
            "request_id": request_id,
            "owner_uid": principal.uid,
            "status": "SCHEDULED",
            "requested_at": timestamp,
            "private_erasure_after": timestamp + timedelta(days=30),
            "preserve_categories": ["safety_reports", "minimum_audit_records"],
        },
    )
    return {"request_id": request_id, "status": "SCHEDULED"}
