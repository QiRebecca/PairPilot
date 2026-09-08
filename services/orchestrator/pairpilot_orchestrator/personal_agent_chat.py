"""Persistent, tool-driving Personal Agent conversation runtime."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Callable, Mapping
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from google import genai
from google.adk.agents import Agent
from google.adk.agents.run_config import (
    RunConfig,
    StreamingMode,  # type: ignore[attr-defined]
)
from google.adk.models import Gemini
from google.adk.runners import Runner
from pairpilot_schemas import CreateUserTaskInput

from pairpilot_orchestrator.auth.authorization import require_task_owner
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.config import Settings
from pairpilot_orchestrator.execution_leases import (
    acquire_execution_lease,
    release_execution_lease,
)
from pairpilot_orchestrator.firestore_session_service import (
    FirestoreSessionService,
)
from pairpilot_orchestrator.generic_agent_runtime import consume_daily_agent_turns
from pairpilot_orchestrator.multi_user_platform import (
    PRODUCTION_NAMESPACE,
    MultiUserStore,
    _clean,
    _public_post_projection,
    agent_id_for_uid,
    create_user_task,
    publish_user_post,
    set_user_post_status,
    stable_id,
)
from pairpilot_orchestrator.v1_foundation import (
    active_community_ids,
    normalize_intent_type,
)
from pairpilot_orchestrator.v2_connections import record_connection_usage
from pairpilot_orchestrator.v2_memory import retrieve_memory_context
from pairpilot_orchestrator.v2_product_glue import ACTION_DEFAULTS, autonomy_level_for

APP_NAME = "pairpilot_real_personal_agent"
MAX_CONTEXT_ITEMS = 20
PERSONAL_AGENT_TURN_TIMEOUT_SECONDS = 90
logger = logging.getLogger(__name__)


class PersonalAgentChatError(Exception):
    """An honest, user-visible Personal Agent turn failure."""


def authoritative_tool_recovery_message(
    completed_tools: list[dict[str, Any]],
) -> str:
    """Report only durable tool outcomes when a post-tool model call is exhausted."""

    names = {str(item.get("name") or "") for item in completed_tools}
    statuses = {
        str(dict(item.get("result") or {}).get("status") or "").upper()
        for item in completed_tools
        if isinstance(item.get("result"), dict)
    }
    if "publish_intent_post" in names and "BLOCKED_BY_AUTONOMY_POLICY" in statuses:
        return (
            "I did not publish the Post because your PUBLISH_POST autonomy policy "
            "is set to Never. The policy decision is saved and you can change it "
            "before trying again."
        )
    if "publish_intent_post" in names and "REQUIRES_HUMAN_CONFIRMATION" in statuses:
        return (
            "I did not publish the Post because this action still needs your "
            "explicit confirmation. The review card is saved and no publication "
            "was fabricated."
        )
    if "publish_intent_post" in names and "PUBLISHED" in statuses:
        return (
            "Your approved Post is published and open for matching. The model "
            "response was interrupted after the authoritative publish succeeded, "
            "so I preserved the completed action and this conversation can continue."
        )
    if names & {"draft_intent_post", "revise_intent_post"}:
        return (
            "I saved the requested Post draft update and added its review card. "
            "The model response was interrupted after the authoritative save "
            "succeeded, so no action was lost and this conversation can continue."
        )
    return (
        "I completed the requested authoritative action before the model response "
        "was interrupted. The saved result is preserved and this conversation can "
        "continue."
    )


def _optional_identifier(value: Any) -> str | None:
    """Normalize nullable persisted identifiers without turning null into "None"."""

    return str(value) if value not in (None, "") else None


def _publish_policy_decision(
    *, publish_level: str, confirmation: str, authorizing_user_content: str
) -> str:
    """Resolve Post publication authority without relying on model prose."""

    if publish_level == "NEVER":
        return "BLOCKED_BY_AUTONOMY_POLICY"
    if publish_level == "AUTOMATIC":
        return "AUTHORIZED"
    normalized_authority = authorizing_user_content.casefold()
    user_authorized = any(
        phrase in normalized_authority
        for phrase in (
            "publish",
            "post it",
            "go ahead",
            "发出去",
            "发布",
            "确认发",
            "可以发",
        )
    )
    if confirmation == "PUBLISH THIS POST" and user_authorized:
        return "AUTHORIZED"
    return "REQUIRES_HUMAN_CONFIRMATION"


def _effective_autonomy_actions(
    global_config: Mapping[str, Any], task_override: Mapping[str, Any]
) -> dict[str, str]:
    """Merge the same action policy layers used by authoritative tools."""

    effective = dict(ACTION_DEFAULTS)
    for source in (global_config, task_override):
        for action, level in dict(source.get("action_levels") or {}).items():
            if action in ACTION_DEFAULTS and level in {
                "AUTOMATIC",
                "ASK_FIRST",
                "NEVER",
            }:
                effective[action] = str(level)
    effective["APPROVE_FINAL_COMMITMENT"] = "ASK_FIRST"
    return effective


def resolve_task_intent_type(requested_type: str, *, event: str, goal: str) -> str:
    """Resolve the canonical V1 type without letting a stale model value abort chat."""

    if requested_type.strip():
        try:
            return normalize_intent_type(requested_type.strip())
        except ValueError:
            pass
    searchable = f"{event} {goal}".casefold()
    keyword_groups = (
        (
            "ROOM_SHARE",
            (
                "roommate",
                "room share",
                "hotel",
                "hostel",
                "住宿",
                "酒店",
                "拼房",
                "室友",
                "房间",
            ),
        ),
        (
            "MEAL_COMPANION",
            (
                "meal",
                "dinner",
                "lunch",
                "breakfast",
                "饭搭子",
                "吃饭",
                "午餐",
                "晚餐",
                "早餐",
            ),
        ),
        (
            "COFFEE_CHAT",
            ("coffee", "café", "cafe", "咖啡", "coffee chat"),
        ),
        (
            "HACKATHON_TEAMMATE",
            ("hackathon", "build week", "teammate", "黑客松", "组队", "队友"),
        ),
    )
    for canonical, keywords in keyword_groups:
        if any(keyword in searchable for keyword in keywords):
            return canonical
    return "EVENT_BUDDY"


def adk_session_id_for_conversation(uid: str, conversation_id: str) -> str:
    return stable_id("adk_session", uid, conversation_id)


async def require_owned_conversation(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    conversation_id: str,
) -> dict[str, Any]:
    conversation = await store.get("conversations", conversation_id)
    if conversation is None or conversation.get("namespace") != PRODUCTION_NAMESPACE:
        raise LookupError("conversation was not found")
    if conversation.get("owner_uid") != principal.uid:
        raise PermissionError("conversation owner required")
    return conversation


async def _directive(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    conversation_id: str,
    action: str,
    entity_ids: list[str],
    task_id: str | None = None,
    explanation: str,
) -> dict[str, Any]:
    await _authorize_directive_entities(
        store, principal, action=action, entity_ids=entity_ids
    )
    directive_id = f"directive_{uuid4().hex}"
    document = {
        "schema_version": 2,
        "namespace": PRODUCTION_NAMESPACE,
        "directive_id": directive_id,
        "owner_uid": principal.uid,
        "conversation_id": conversation_id,
        "task_id": task_id,
        "action": action,
        "presentation": "INLINE_CARD",
        "entity_ids": entity_ids,
        "explanation": explanation,
        "created_at": datetime.now(UTC),
    }
    await store.create("presentation_directives", directive_id, document)
    return document


async def _authorize_directive_entities(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    action: str,
    entity_ids: list[str],
) -> None:
    """Reject model-supplied entity IDs before a directive is persisted."""

    if action == "FILTER_EXPLORE":
        return
    rules = {
        "OPEN_TASK": ("task_workspaces", "owner_uid"),
        "SHOW_TASK_STATUS": ("task_workspaces", "owner_uid"),
        "SHOW_POST": ("intent_posts", "public_or_owner"),
        "SHOW_POST_DETAIL": ("intent_posts", "public_or_owner"),
        "SHOW_RELATED_POSTS": ("intent_posts", "public_or_owner"),
        "SHOW_CANDIDATE_POOL": ("candidate_assessments", "owner_uid"),
        "SHOW_CANDIDATE_COMPARISON": ("candidate_assessments", "owner_uid"),
        "SHOW_DECISION": ("decisions", "owner_uid"),
        "SHOW_ROOM": ("coordination_rooms", "participant_uids"),
        "OPEN_COORDINATION_ROOM": ("coordination_rooms", "participant_uids"),
        "SHOW_PROPOSAL": ("proposals", "participant_uids"),
        "SHOW_MATCH": ("matches", "participant_uids"),
        "SHOW_CONNECTION": ("relationships", "owner_uid"),
        "SHOW_RELATIONSHIP": ("relationships", "owner_uid"),
        "SHOW_NETWORK_PATH": ("relationships", "owner_uid"),
        "SHOW_MEMORY": ("memories", "owner_uid"),
        "SHOW_COMMUNITY": ("communities", "public"),
    }
    rule = rules.get(action)
    if rule is None:
        raise PermissionError("presentation action is not allowlisted")
    collection, authority = rule
    for entity_id in entity_ids:
        if action in {"OPEN_TASK", "SHOW_TASK_STATUS"} and entity_id.startswith(
            "intent_"
        ):
            intent = await store.get("intent_private_data", entity_id)
            if intent is None or intent.get("owner_uid") != principal.uid:
                raise PermissionError("presentation intent is not owner-authorized")
            continue
        if authority == "public_or_owner" and entity_id.startswith("task_"):
            task = await store.get("task_workspaces", entity_id)
            if task is None or task.get("owner_uid") != principal.uid:
                raise PermissionError("presentation task is not owner-authorized")
            continue
        document = await store.get(collection, entity_id)
        if document is None or document.get("namespace") != PRODUCTION_NAMESPACE:
            raise PermissionError("presentation entity was not found")
        if authority == "owner_uid" and document.get("owner_uid") != principal.uid:
            raise PermissionError("presentation entity is not owner-authorized")
        if authority == "participant_uids" and principal.uid not in {
            str(item) for item in document.get("participant_uids", [])
        }:
            raise PermissionError("presentation entity is not participant-authorized")
        if authority == "public_or_owner" and not (
            document.get("owner_uid") == principal.uid
            or document.get("status")
            in {"OPEN", "NEGOTIATING", "HELD", "AWAITING_APPROVAL"}
        ):
            raise PermissionError("presentation Post is not public")
        if authority == "public" and document.get("status") == "ARCHIVED":
            raise PermissionError("presentation Community is not visible")


async def _task(
    store: MultiUserStore, principal: AuthenticatedPrincipal, task_id: str
) -> dict[str, Any]:
    task = await store.get("task_workspaces", task_id)
    if task is None or task.get("namespace") != PRODUCTION_NAMESPACE:
        raise ValueError("task was not found")
    require_task_owner(principal, task)
    return task


async def _scoped_context(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    conversation: dict[str, Any],
) -> dict[str, Any]:
    task_id = _optional_identifier(conversation.get("task_id"))
    tasks = await store.query_documents(
        "task_workspaces", filters=[("owner_uid", "EQUAL", principal.uid)]
    )
    decisions = await store.query_documents(
        "decisions", filters=[("owner_uid", "EQUAL", principal.uid)]
    )
    permitted_memories = await retrieve_memory_context(
        store,
        principal,
        task_id=task_id,
        purpose="PERSONAL_AGENT_CONTEXT",
    )
    relationships = await store.query_documents(
        "relationships", filters=[("owner_uid", "EQUAL", principal.uid)]
    )
    autonomy = await store.get("user_autonomy_configs", principal.uid) or {}
    autonomy_override: dict[str, Any] = {}
    if task_id is not None:
        override_id = stable_id("autonomy_override", principal.uid, task_id)
        autonomy_override = (
            await store.get("autonomy_task_overrides", override_id) or {}
        )
    memberships = await active_community_ids(store, principal.uid)
    task_index = [
        {
            "task_id": item.get("task_id"),
            "title": item.get("title"),
            "status": item.get("status"),
            "task_type": item.get("task_type"),
            "updated_at": item.get("updated_at"),
        }
        for item in tasks[:MAX_CONTEXT_ITEMS]
    ]
    context: dict[str, Any] = {
        "conversationKind": conversation.get("kind"),
        "taskIndex": task_index,
        "openDecisions": [
            {
                "decision_id": item.get("decision_id"),
                "task_id": item.get("task_id"),
                "type": item.get("type"),
                "title": item.get("title"),
            }
            for item in decisions
            if item.get("status") == "OPEN"
        ][:MAX_CONTEXT_ITEMS],
        "confirmedMemory": permitted_memories[:MAX_CONTEXT_ITEMS],
        "relationships": [
            {
                "relationship_id": item.get("relationship_id"),
                "peer_agent_id": item.get("peer_agent_id"),
                "relation_type": item.get("relation_type"),
                "successful_plans": item.get("successful_plans"),
            }
            for item in relationships[:MAX_CONTEXT_ITEMS]
        ],
        "autonomyMode": autonomy.get("default_mode", "COPILOT"),
        "autonomyActions": _effective_autonomy_actions(autonomy, autonomy_override),
        "activeCommunityIds": sorted(memberships),
    }
    if task_id is None:
        return context
    selected = await _task(store, principal, task_id)
    private_intent = await store.get("intent_private_data", str(selected["intent_id"]))
    posts = await store.query_documents(
        "intent_posts", filters=[("owner_uid", "EQUAL", principal.uid)]
    )
    rooms = await store.query_documents(
        "coordination_rooms",
        filters=[("participant_uids", "ARRAY_CONTAINS", principal.uid)],
    )
    assessments = await store.query_documents(
        "candidate_assessments", filters=[("owner_uid", "EQUAL", principal.uid)]
    )
    context.update(
        selectedTask=_clean(selected),
        privateIntent=_clean(private_intent or {}),
        ownPost=next(
            (
                _public_post_projection(item)
                for item in posts
                if item.get("task_id") == task_id
            ),
            None,
        ),
        rooms=[
            {
                key: value
                for key, value in _clean(item).items()
                if key not in {"participant_uids", "revoked_participant_uids"}
            }
            for item in rooms
            if task_id in {item.get("source_task_id"), item.get("target_task_id")}
        ],
        candidateAssessments=[
            _clean(item) for item in assessments if item.get("task_id") == task_id
        ][:MAX_CONTEXT_ITEMS],
    )
    return context


def _build_tools(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    conversation: dict[str, Any],
    *,
    authorizing_user_content: str,
) -> list[Callable[..., Any]]:
    conversation_id = str(conversation["conversation_id"])
    scoped_task_id = _optional_identifier(conversation.get("task_id"))

    async def create_task_workspace(
        title: str,
        goal: str,
        event: str,
        location: str,
        date_start: str,
        date_end: str,
        public_requirements: list[str],
        maximum_additional_cost_usd: int = 0,
        partial_date_overlap_allowed: bool = True,
        intent_type: str = "",
        community_id: str = "",
    ) -> dict[str, Any]:
        """Create a private task in one active community after details exist."""

        if scoped_task_id is not None:
            return {"status": "REJECTED", "reason": "use global conversation"}
        memberships = await active_community_ids(store, principal.uid)
        profile = await store.get("users", principal.uid) or {}
        preferred = [
            str(item)
            for item in profile.get("community_ids", [])
            if str(item) in memberships
        ]
        selected_community_id = community_id or next(
            iter(preferred or sorted(memberships)), ""
        )
        if selected_community_id not in memberships:
            return {
                "status": "REJECTED",
                "reason": "COMMUNITY_MEMBERSHIP_REQUIRED",
                "available_community_ids": sorted(memberships),
            }
        body = CreateUserTaskInput(
            title=title,
            task_type=resolve_task_intent_type(
                intent_type,
                event=event,
                goal=goal,
            ),
            goal=goal,
            event=event,
            location=location,
            date_start=date.fromisoformat(date_start),
            date_end=date.fromisoformat(date_end),
            public_requirements=public_requirements,
            maximum_additional_cost_usd=maximum_additional_cost_usd,
            partial_date_overlap_allowed=partial_date_overlap_allowed,
            community_id=selected_community_id,
        )
        task = await create_user_task(store, principal, body)
        directive = await _directive(
            store,
            principal,
            conversation_id=conversation_id,
            task_id=str(task["task_id"]),
            action="OPEN_TASK",
            entity_ids=[str(task["task_id"]), str(task["intent_id"])],
            explanation="Open the Agent-created private task and review its draft.",
        )
        return {
            "status": "CREATED",
            "task_id": task["task_id"],
            "conversation_id": task["conversation_id"],
            "intent_id": task["intent_id"],
            "presentation_directive_id": directive["directive_id"],
        }

    async def list_task_summaries() -> dict[str, Any]:
        """List this owner's task IDs, titles and current authoritative status."""

        items = await store.query_documents(
            "task_workspaces", filters=[("owner_uid", "EQUAL", principal.uid)]
        )
        return {
            "tasks": [
                {
                    "task_id": item.get("task_id"),
                    "title": item.get("title"),
                    "status": item.get("status"),
                    "updated_at": item.get("updated_at"),
                }
                for item in items[:MAX_CONTEXT_ITEMS]
            ]
        }

    async def inspect_task_status(task_id: str) -> dict[str, Any]:
        """Inspect one owned task plus its rooms and unresolved decisions."""

        selected = await _task(store, principal, task_id)
        decisions = await store.query_documents(
            "decisions", filters=[("owner_uid", "EQUAL", principal.uid)]
        )
        rooms = await store.query_documents(
            "coordination_rooms",
            filters=[("participant_uids", "ARRAY_CONTAINS", principal.uid)],
        )
        return {
            "task": {
                key: value
                for key, value in _clean(selected).items()
                if key not in {"owner_uid"}
            },
            "open_decisions": [
                _clean(item)
                for item in decisions
                if item.get("task_id") == task_id and item.get("status") == "OPEN"
            ],
            "rooms": [
                {
                    "room_id": item.get("room_id"),
                    "status": item.get("status"),
                    "room_type": item.get("room_type"),
                }
                for item in rooms
                if task_id in {item.get("source_task_id"), item.get("target_task_id")}
            ],
        }

    async def route_to_task(task_id: str) -> dict[str, Any]:
        """Create an authoritative inline link to one owned task."""

        await _task(store, principal, task_id)
        directive = await _directive(
            store,
            principal,
            conversation_id=conversation_id,
            task_id=task_id,
            action="OPEN_TASK",
            entity_ids=[task_id],
            explanation="Open the selected task workspace.",
        )
        return {
            "status": "READY",
            "task_id": task_id,
            "presentation_directive_id": directive["directive_id"],
        }

    async def inspect_decision_inbox() -> dict[str, Any]:
        """List unresolved decisions for this owner."""

        items = await store.query_documents(
            "decisions", filters=[("owner_uid", "EQUAL", principal.uid)]
        )
        return {
            "decisions": [
                _clean(item) for item in items if item.get("status") == "OPEN"
            ]
        }

    async def inspect_relationship(peer_agent_id: str) -> dict[str, Any]:
        """Inspect an owner-scoped relationship with one peer Agent."""

        items = await store.query_documents(
            "relationships", filters=[("owner_uid", "EQUAL", principal.uid)]
        )
        relationship = next(
            (item for item in items if item.get("peer_agent_id") == peer_agent_id),
            None,
        )
        if relationship is None:
            return {"relationship": None, "context_applicable": False}
        usage = await record_connection_usage(
            store,
            principal,
            connection_id=str(relationship["relationship_id"]),
            task_id=scoped_task_id or None,
            purpose="INSPECT",
        )
        return {
            "relationship": {
                key: value
                for key, value in relationship.items()
                if key
                in {
                    "relationship_id",
                    "peer_agent_id",
                    "relation_type",
                    "plans_committed",
                    "successful_plans",
                    "cancellation_history",
                    "commitment_inaccuracy_reports",
                    "task_type_compatibility",
                    "introduction_path",
                    "last_interaction_at",
                }
            },
            "context_applicable": usage["context_applicable"],
            "usage_id": usage["usage_id"],
        }

    async def inspect_memory(query: str) -> dict[str, Any]:
        """Search this owner's permitted memory by a short text query."""

        return {
            "memories": await retrieve_memory_context(
                store,
                principal,
                task_id=scoped_task_id,
                purpose="PERSONAL_AGENT_INSPECT_MEMORY",
                query=query,
            )
        }

    async def propose_memory(
        content: str,
        scope: str,
        memory_type: str = "WORKING_BELIEF",
        topic_key: str = "",
        contradicts_memory_id: str = "",
    ) -> dict[str, Any]:
        """Propose, but do not silently confirm, an owner-scoped memory."""

        memory_id = f"memory_{uuid4().hex}"
        allowed_types = {
            "CONFIRMED_USER_MEMORY",
            "TASK_MEMORY",
            "EPISODIC_MEMORY",
            "RELATIONAL_MEMORY",
            "WORKING_BELIEF",
        }
        normalized_type = memory_type.upper()
        if normalized_type not in allowed_types:
            normalized_type = "WORKING_BELIEF"
        document = {
            "schema_version": 3,
            "namespace": PRODUCTION_NAMESPACE,
            "memory_id": memory_id,
            "owner_uid": principal.uid,
            "owner_agent_id": agent_id_for_uid(principal.uid),
            "content": content,
            "scope": scope,
            "memory_type": normalized_type,
            "topic_key": topic_key.strip() or None,
            "contradicts_memory_ids": (
                [contradicts_memory_id] if contradicts_memory_id else []
            ),
            "confidence": "AGENT_PROPOSED_UNCONFIRMED",
            "sensitivity": "PRIVATE",
            "status": "PROPOSED",
            "confirmation_status": "PROPOSED",
            "created_at": datetime.now(UTC),
        }
        await store.create("memories", memory_id, document)
        directive = await _directive(
            store,
            principal,
            conversation_id=conversation_id,
            action="SHOW_MEMORY",
            entity_ids=[memory_id],
            explanation="Review the Agent-proposed memory before confirming it.",
        )
        return {
            "status": "PROPOSED",
            "memory_id": memory_id,
            "presentation_directive_id": directive["directive_id"],
        }

    async def emit_presentation_directive(
        action: str, entity_id: str, explanation: str
    ) -> dict[str, Any]:
        """Show an allowlisted authoritative entity as an inline UI card."""

        allowed = {
            "OPEN_TASK",
            "SHOW_TASK_STATUS",
            "SHOW_POST",
            "SHOW_POST_DETAIL",
            "SHOW_RELATED_POSTS",
            "SHOW_CANDIDATE_POOL",
            "SHOW_CANDIDATE_COMPARISON",
            "SHOW_DECISION",
            "SHOW_ROOM",
            "OPEN_COORDINATION_ROOM",
            "SHOW_PROPOSAL",
            "SHOW_MATCH",
            "SHOW_CONNECTION",
            "SHOW_NETWORK_PATH",
            "SHOW_MEMORY",
            "SHOW_COMMUNITY",
            "FILTER_EXPLORE",
        }
        if action not in allowed:
            return {"status": "REJECTED", "reason": "action not allowlisted"}
        directive = await _directive(
            store,
            principal,
            conversation_id=conversation_id,
            task_id=scoped_task_id,
            action=action,
            entity_ids=[entity_id],
            explanation=explanation,
        )
        return {
            "status": "CREATED",
            "presentation_directive_id": directive["directive_id"],
        }

    global_tools: list[Callable[..., Any]] = [
        create_task_workspace,
        list_task_summaries,
        inspect_task_status,
        route_to_task,
        inspect_decision_inbox,
        inspect_relationship,
        inspect_memory,
        propose_memory,
        emit_presentation_directive,
    ]
    if scoped_task_id is None:
        return global_tools

    async def draft_intent_post(
        public_title: str,
        public_summary: str,
        public_requirements: list[str],
    ) -> dict[str, Any]:
        """Draft or revise public fields without publishing them."""

        task = await _task(store, principal, scoped_task_id)
        private = await store.get("intent_private_data", str(task["intent_id"]))
        if private is None:
            raise ValueError("private intent was not found")
        clean = _clean(private)
        draft = dict(clean.get("public_draft", {}))
        draft.update(
            public_title=public_title,
            public_summary=public_summary,
            public_requirements=public_requirements,
        )
        clean.update(public_draft=draft, updated_at=datetime.now(UTC))
        await store.upsert("intent_private_data", str(task["intent_id"]), clean)
        directive = await _directive(
            store,
            principal,
            conversation_id=conversation_id,
            task_id=scoped_task_id,
            action="SHOW_POST",
            entity_ids=[str(task["intent_id"])],
            explanation="Review the Agent-created post draft before publication.",
        )
        return {
            "status": "DRAFTED",
            "intent_id": task["intent_id"],
            "presentation_directive_id": directive["directive_id"],
        }

    async def revise_intent_post(
        public_title: str,
        public_summary: str,
        public_requirements: list[str],
        maximum_additional_cost_usd: int,
    ) -> dict[str, Any]:
        """Revise task boundaries and invalidate any stale active proposal."""

        result = await draft_intent_post(
            public_title, public_summary, public_requirements
        )
        task = await _task(store, principal, scoped_task_id)
        private = await store.get("intent_private_data", str(task["intent_id"]))
        assert private is not None
        clean = _clean(private)
        boundaries = dict(clean.get("agent_only_constraints", {}))
        boundaries["maximum_additional_cost_usd"] = maximum_additional_cost_usd
        clean.update(agent_only_constraints=boundaries, updated_at=datetime.now(UTC))
        await store.upsert("intent_private_data", str(task["intent_id"]), clean)
        proposal_id = str(task.get("active_proposal_id", ""))
        if proposal_id:
            proposal = await store.get("proposals", proposal_id)
            if proposal is not None and proposal.get("status") == "AWAITING_HUMANS":
                proposal_clean = _clean(proposal)
                proposal_clean.update(
                    status="REQUIRES_REEVALUATION",
                    invalidated_reason="owner_boundary_changed",
                    updated_at=datetime.now(UTC),
                )
                await store.upsert("proposals", proposal_id, proposal_clean)
        return {
            **result,
            "maximum_additional_cost_usd": maximum_additional_cost_usd,
            "proposal_re_evaluation_required": bool(proposal_id),
        }

    async def publish_intent_post(
        public_title: str,
        public_summary: str,
        public_requirements: list[str],
        confirmation: str,
    ) -> dict[str, Any]:
        """Publish only with the owner's exact explicit confirmation phrase."""

        task = await _task(store, principal, scoped_task_id)
        if str(task.get("status") or "").upper() in {
            "CANCELLED",
            "CLOSED",
            "COMPLETED",
        }:
            return {
                "status": "TASK_NOT_ACTIVE",
                "task_id": scoped_task_id,
                "message": (
                    "This Request is closed. Create or select an active Request "
                    "before publishing a Post."
                ),
            }

        publish_level = await autonomy_level_for(
            store,
            owner_uid=principal.uid,
            action="PUBLISH_POST",
            task_id=scoped_task_id,
        )
        decision = _publish_policy_decision(
            publish_level=publish_level,
            confirmation=confirmation,
            authorizing_user_content=authorizing_user_content,
        )
        if decision == "BLOCKED_BY_AUTONOMY_POLICY":
            directive = await _directive(
                store,
                principal,
                conversation_id=conversation_id,
                task_id=scoped_task_id,
                action="SHOW_POST",
                entity_ids=[scoped_task_id],
                explanation="Publication is disabled by the owner's autonomy policy.",
            )
            return {
                "status": "BLOCKED_BY_AUTONOMY_POLICY",
                "action": "PUBLISH_POST",
                "policy_level": "NEVER",
                "presentation_directive_id": directive["directive_id"],
            }
        if decision == "REQUIRES_HUMAN_CONFIRMATION":
            directive = await _directive(
                store,
                principal,
                conversation_id=conversation_id,
                task_id=scoped_task_id,
                action="SHOW_POST",
                entity_ids=[scoped_task_id],
                explanation="Publication needs the owner's exact confirmation.",
            )
            return {
                "status": "REQUIRES_HUMAN_CONFIRMATION",
                "required_confirmation": "PUBLISH THIS POST",
                "presentation_directive_id": directive["directive_id"],
            }
        post = await publish_user_post(
            store,
            principal,
            task_id=scoped_task_id,
            public_title=public_title,
            public_summary=public_summary,
            public_requirements=public_requirements,
        )
        return {"status": "PUBLISHED", "post": post}

    async def _post_status(status: str) -> dict[str, Any]:
        task = await _task(store, principal, scoped_task_id)
        post = await set_user_post_status(
            store, principal, intent_id=str(task["intent_id"]), status=status
        )
        return {"status": status, "post": post}

    async def pause_intent_post() -> dict[str, Any]:
        """Pause this task's discoverable post."""

        return await _post_status("PAUSED")

    async def resume_intent_post() -> dict[str, Any]:
        """Resume this task's paused post."""

        return await _post_status("OPEN")

    async def close_intent_post() -> dict[str, Any]:
        """Close this task's post to new contacts."""

        return await _post_status("CLOSED")

    async def search_open_intents() -> dict[str, Any]:
        """Search current public posts without exposing private owner data."""

        posts = await store.query_documents(
            "intent_posts", filters=[("status", "EQUAL", "OPEN")]
        )
        return {
            "posts": [
                _public_post_projection(item)
                for item in posts
                if item.get("owner_uid") != principal.uid
                and item.get("namespace") == PRODUCTION_NAMESPACE
            ][:10]
        }

    async def inspect_candidate_assessments() -> dict[str, Any]:
        """Inspect persisted candidate evidence for this task."""

        items = await store.query_documents(
            "candidate_assessments", filters=[("owner_uid", "EQUAL", principal.uid)]
        )
        return {
            "assessments": [
                _clean(item) for item in items if item.get("task_id") == scoped_task_id
            ]
        }

    async def show_candidate_comparison(
        candidate_name_or_id: str,
    ) -> dict[str, Any]:
        """Inspect a candidate and emit one authoritative comparison card."""

        result = await inspect_candidate_assessments()
        needle = candidate_name_or_id.casefold()
        assessment = next(
            (
                item
                for item in result["assessments"]
                if needle
                in json.dumps(item, default=str, separators=(",", ":")).casefold()
            ),
            None,
        )
        if assessment is None:
            return {"status": "NOT_FOUND", "candidate": candidate_name_or_id}
        assessment_id = str(assessment["assessment_id"])
        directive = await _directive(
            store,
            principal,
            conversation_id=conversation_id,
            task_id=scoped_task_id,
            action="SHOW_CANDIDATE_COMPARISON",
            entity_ids=[assessment_id],
            explanation="Show the current authoritative candidate comparison.",
        )
        return {
            "status": "READY",
            "assessment": assessment,
            "presentation_directive_id": directive["directive_id"],
        }

    async def inspect_public_intent(intent_id: str) -> dict[str, Any]:
        """Inspect one public intent projection by ID."""

        post = await store.get("intent_posts", intent_id)
        return {"post": _public_post_projection(post or {}) if post else None}

    async def send_private_task_instruction(content: str) -> dict[str, Any]:
        """Persist an owner-private instruction that must never be sent verbatim."""

        instruction_id = f"instruction_{uuid4().hex}"
        await store.create(
            "task_instructions",
            instruction_id,
            {
                "namespace": PRODUCTION_NAMESPACE,
                "instruction_id": instruction_id,
                "owner_uid": principal.uid,
                "task_id": scoped_task_id,
                "content": content,
                "visibility": "PRIVATE_USER_AGENT",
                "created_at": datetime.now(UTC),
            },
        )
        return {"status": "STORED_PRIVATE", "instruction_id": instruction_id}

    async def calculate_plan_cost(
        nightly_cost_usd: int, nights: int, owner_share_fraction: float
    ) -> dict[str, Any]:
        """Calculate the owner's deterministic additional plan cost."""

        if nights < 0 or not 0 <= owner_share_fraction <= 1:
            return {"status": "REJECTED", "reason": "invalid cost inputs"}
        return {
            "status": "CALCULATED",
            "cost_usd": round(nightly_cost_usd * nights * owner_share_fraction, 2),
        }

    async def request_human_decision() -> dict[str, Any]:
        """Show unresolved authoritative decisions for this task."""

        decisions = await inspect_decision_inbox()
        task_decisions = [
            item
            for item in decisions["decisions"]
            if item.get("task_id") == scoped_task_id
        ]
        directive_id: str | None = None
        if task_decisions:
            directive = await _directive(
                store,
                principal,
                conversation_id=conversation_id,
                task_id=scoped_task_id,
                action="SHOW_DECISION",
                entity_ids=[str(task_decisions[0]["decision_id"])],
                explanation="Review the current authoritative decision.",
            )
            directive_id = str(directive["directive_id"])
        return {
            "decisions": task_decisions,
            "presentation_directive_id": directive_id,
        }

    async def contact_peer_agent(intent_id: str) -> dict[str, Any]:
        """Schedule bounded background contact for a discovered public intent."""

        task = await _task(store, principal, scoped_task_id)
        await store.write_event(
            event_type="agent.contact.requested.v3",
            run_id=scoped_task_id,
            producer=agent_id_for_uid(principal.uid),
            payload={
                "taskId": scoped_task_id,
                "sourceIntentId": task["intent_id"],
                "targetIntentId": intent_id,
            },
            idempotency_key=f"v3:{scoped_task_id}:contact:{intent_id}",
        )
        return {"status": "SCHEDULED", "target_intent_id": intent_id}

    async def open_coordination_room() -> dict[str, Any]:
        """Show existing authorized rooms for this task; never fabricate one."""

        status = await inspect_task_status(scoped_task_id)
        rooms = status["rooms"]
        if not rooms:
            return {"status": "NO_ROOM", "rooms": []}
        directive = await _directive(
            store,
            principal,
            conversation_id=conversation_id,
            task_id=scoped_task_id,
            action="SHOW_ROOM",
            entity_ids=[str(rooms[0]["room_id"])],
            explanation="Open the existing authorized coordination room.",
        )
        return {
            "status": "READY",
            "rooms": rooms,
            "presentation_directive_id": directive["directive_id"],
        }

    async def request_warm_introduction(peer_agent_id: str) -> dict[str, Any]:
        """Check relationship evidence before proposing a warm introduction."""

        relationship = await inspect_relationship(peer_agent_id)
        if relationship["relationship"] and not relationship["context_applicable"]:
            return {"status": "CONTEXT_MISMATCH", **relationship}
        return {
            "status": "ELIGIBLE"
            if relationship["relationship"]
            else "NO_RELATIONSHIP_EVIDENCE",
            **relationship,
        }

    async def send_intent_scoped_a2a_message(
        target_intent_id: str, minimum_necessary_message: str
    ) -> dict[str, Any]:
        """Schedule a minimum-necessary A2A message through the background worker."""

        request_id = f"a2a_request_{uuid4().hex}"
        task = await _task(store, principal, scoped_task_id)
        await store.create(
            "a2a_requests",
            request_id,
            {
                "namespace": PRODUCTION_NAMESPACE,
                "request_id": request_id,
                "owner_uid": principal.uid,
                "source_task_id": scoped_task_id,
                "source_intent_id": task["intent_id"],
                "target_intent_id": target_intent_id,
                "minimum_necessary_message": minimum_necessary_message,
                "status": "QUEUED",
                "created_at": datetime.now(UTC),
            },
        )
        await store.write_event(
            event_type="agent.contact.requested.v3",
            run_id=scoped_task_id,
            producer=agent_id_for_uid(principal.uid),
            payload={
                "taskId": scoped_task_id,
                "sourceIntentId": task["intent_id"],
                "targetIntentId": target_intent_id,
                "a2aRequestId": request_id,
            },
            idempotency_key=f"v3:{scoped_task_id}:a2a:{target_intent_id}",
        )
        return {"status": "QUEUED", "request_id": request_id}

    async def update_candidate_assessment(
        target_intent_id: str, summary: str, disposition: str
    ) -> dict[str, Any]:
        """Persist a task-scoped assessment while treating peer claims as reported."""

        assessment_id = stable_id(
            "candidate_assessment", scoped_task_id, target_intent_id
        )
        document = {
            "namespace": PRODUCTION_NAMESPACE,
            "assessment_id": assessment_id,
            "owner_uid": principal.uid,
            "task_id": scoped_task_id,
            "target_intent_id": target_intent_id,
            "summary": summary,
            "disposition": disposition,
            "evidence_status": "REPORTED_CLAIM",
            "updated_at": datetime.now(UTC),
        }
        await store.upsert("candidate_assessments", assessment_id, document)
        return {"status": "UPDATED", "assessment_id": assessment_id}

    async def create_proposal(target_intent_id: str) -> dict[str, Any]:
        """Request infrastructure evaluation; do not directly commit a proposal."""

        task = await _task(store, principal, scoped_task_id)
        await store.write_event(
            event_type="proposal.evaluation.requested.v3",
            run_id=scoped_task_id,
            producer=agent_id_for_uid(principal.uid),
            payload={
                "sourceIntentId": task["intent_id"],
                "targetIntentId": target_intent_id,
            },
            idempotency_key=f"v3:{scoped_task_id}:proposal:{target_intent_id}",
        )
        return {"status": "EVALUATION_SCHEDULED", "target_intent_id": target_intent_id}

    async def revalidate_offer() -> dict[str, Any]:
        """Read current proposal state; infrastructure owns revalidation."""

        task = await _task(store, principal, scoped_task_id)
        proposal_id = str(task.get("active_proposal_id", ""))
        proposal = await store.get("proposals", proposal_id) if proposal_id else None
        return {"status": "CURRENT_STATE", "proposal": _clean(proposal or {})}

    async def withdraw_from_candidate(target_intent_id: str) -> dict[str, Any]:
        """Persist a task-scoped withdrawal from one candidate."""

        withdrawal_id = stable_id("withdrawal", scoped_task_id, target_intent_id)
        await store.upsert(
            "candidate_withdrawals",
            withdrawal_id,
            {
                "namespace": PRODUCTION_NAMESPACE,
                "withdrawal_id": withdrawal_id,
                "owner_uid": principal.uid,
                "task_id": scoped_task_id,
                "target_intent_id": target_intent_id,
                "created_at": datetime.now(UTC),
            },
        )
        return {"status": "WITHDRAWN", "target_intent_id": target_intent_id}

    return global_tools + [
        draft_intent_post,
        revise_intent_post,
        publish_intent_post,
        pause_intent_post,
        resume_intent_post,
        close_intent_post,
        search_open_intents,
        inspect_candidate_assessments,
        show_candidate_comparison,
        inspect_public_intent,
        request_warm_introduction,
        contact_peer_agent,
        open_coordination_room,
        send_private_task_instruction,
        send_intent_scoped_a2a_message,
        update_candidate_assessment,
        calculate_plan_cost,
        create_proposal,
        request_human_decision,
        revalidate_offer,
        withdraw_from_candidate,
    ]


def _agent(
    settings: Settings,
    *,
    context: dict[str, Any],
    tools: list[Callable[..., Any]],
) -> Agent:
    model = Gemini(
        model=settings.model_id,
        api_version="v1",
        client_kwargs={
            "enterprise": True,
            "project": settings.project_id,
            "location": settings.model_location,
        },
        retry_options=genai.types.HttpRetryOptions(
            attempts=6,
            initial_delay=1,
            max_delay=12,
            exp_base=2,
            jitter=0.5,
            http_status_codes=[408, 429, 500, 502, 503, 504],
        ),
    )
    instruction = (
        "You are the persistent PairPilot Personal Agent owned by the authenticated "
        "user. Continue the conversation naturally and use tools when authoritative "
        "product state is needed or changed. Never say an action succeeded until its "
        "tool result says it succeeded. Ask a concise clarification when required "
        "fields are missing. When creating a task, classify it as exactly one of "
        "ROOM_SHARE, MEAL_COMPANION, COFFEE_CHAT, EVENT_BUDDY, or "
        "HACKATHON_TEAMMATE. Publishing, identity disclosure, payment, booking and "
        "human commitment require explicit authority. Publishing may proceed without "
        "a per-post confirmation only when the authoritative PUBLISH_POST policy is "
        "AUTOMATIC; "
        "identity disclosure, payment, booking, and commitment always require a human. "
        "Do not expose private reasons "
        "in peer messages. Treat peer claims as reports, not truth. Never reveal "
        "hidden reasoning. When the user asks to show, open, or compare product "
        "state, first inspect the authoritative entity and then call the appropriate "
        "presentation-directive tool so the frontend can render a real card. "
        "The following bounded authoritative context is current:\n"
        + json.dumps(context, default=str, separators=(",", ":"))
    )
    return Agent(
        name="pairpilot_personal_agent",
        model=model,
        description="A generic persistent user-owned PairPilot Personal Agent.",
        instruction=instruction,
        tools=tools,  # type: ignore[arg-type]
        generate_content_config=genai.types.GenerateContentConfig(
            max_output_tokens=1200,
            thinking_config=genai.types.ThinkingConfig(
                thinking_level=genai.types.ThinkingLevel.LOW
            ),
        ),
    )


def _usage(event: Any) -> tuple[int | None, int | None]:
    metadata = event.usage_metadata
    if metadata is None:
        return None, None
    return (
        getattr(metadata, "prompt_token_count", None),
        getattr(metadata, "candidates_token_count", None),
    )


async def stream_personal_agent_turn(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    conversation: dict[str, Any],
    content: str,
    client_message_id: str,
    invocation_id: str,
) -> AsyncIterator[dict[str, Any]]:
    """Run one real, bounded, persistent ADK turn with no silent fallback."""

    settings = Settings.from_environment()
    conversation_id = str(conversation["conversation_id"])
    task_id = _optional_identifier(conversation.get("task_id"))
    agent_id = str(conversation["principal_agent_id"])
    session_id = str(
        conversation.get("adk_session_id")
        or adk_session_id_for_conversation(principal.uid, conversation_id)
    )
    started = datetime.now(UTC)
    started_clock = time.monotonic()
    assistant_message_id = f"message_{uuid4().hex}"
    invocation: dict[str, Any] = {
        "namespace": PRODUCTION_NAMESPACE,
        "invocation_id": invocation_id,
        "owner_uid": principal.uid,
        "personal_agent_id": agent_id,
        "conversation_id": conversation_id,
        "task_id": task_id,
        "client_message_id": client_message_id,
        "assistant_message_id": assistant_message_id,
        "adk_session_id": session_id,
        "adk_invocation_id": invocation_id,
        "model_id": settings.model_id,
        "execution_mode": settings.execution_mode,
        "status": "RUNNING",
        "started_at": started,
        "tool_call_ids": [],
        "presentation_directive_ids": [],
    }
    await store.create("agent_invocations", invocation_id, invocation)
    yield {
        "type": "message.accepted",
        "invocation_id": invocation_id,
        "client_message_id": client_message_id,
    }
    yield {
        "type": "agent.started",
        "invocation_id": invocation_id,
        "adk_session_id": session_id,
        "model_id": settings.model_id,
        "execution_mode": settings.execution_mode,
    }
    lease = None
    tool_call_ids: list[str] = []
    completed_tools: list[dict[str, Any]] = []
    directive_ids: list[str] = []
    input_tokens: int | None = None
    output_tokens: int | None = None
    partial_fragments: list[str] = []
    final_text = ""
    completion_mode = "LIVE_MODEL"
    recovered_model_error: str | None = None
    try:
        lease = await acquire_execution_lease(
            store,
            resource_id=f"conversation:{conversation_id}",
            lease_owner=f"chat-{invocation_id}",
        )
        if lease is None:
            raise PersonalAgentChatError("another Agent turn is already active")
        await consume_daily_agent_turns(store, [principal.uid])
        session_service = FirestoreSessionService(store)
        session = await session_service.get_session(
            app_name=APP_NAME,
            user_id=principal.uid,
            session_id=session_id,
        )
        if session is None:
            await session_service.create_session(
                app_name=APP_NAME,
                user_id=principal.uid,
                session_id=session_id,
                state={
                    "conversation_id": conversation_id,
                    "task_id": task_id,
                    "personal_agent_id": agent_id,
                },
            )
            conversation_clean = _clean(conversation)
            if conversation_clean.get("kind") == "GLOBAL_PERSONAL_AGENT":
                conversation_clean.pop("task_id", None)
            conversation_clean.update(
                adk_session_id=session_id,
                updated_at=datetime.now(UTC),
            )
            await store.upsert("conversations", conversation_id, conversation_clean)
        context = await _scoped_context(store, principal, conversation)
        runner = Runner(
            app_name=APP_NAME,
            agent=_agent(
                settings,
                context=context,
                tools=_build_tools(
                    store,
                    principal,
                    conversation,
                    authorizing_user_content=content,
                ),
            ),
            session_service=session_service,
        )
        adk_events = runner.run_async(
            user_id=principal.uid,
            session_id=session_id,
            invocation_id=invocation_id,
            new_message=genai.types.Content(
                role="user", parts=[genai.types.Part(text=content)]
            ),
            run_config=RunConfig(
                streaming_mode=StreamingMode.SSE,
                max_llm_calls=8,
            ),
        )
        turn_deadline = time.monotonic() + PERSONAL_AGENT_TURN_TIMEOUT_SECONDS
        while True:
            try:
                remaining = turn_deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError
                event = await asyncio.wait_for(anext(adk_events), timeout=remaining)
            except StopAsyncIteration:
                break
            except TimeoutError as exc:
                if completed_tools:
                    recovered_model_error = "PERSONAL_AGENT_TURN_TIMEOUT"
                    completion_mode = "AUTHORITATIVE_TOOL_RECOVERY"
                    final_text = authoritative_tool_recovery_message(completed_tools)
                    yield {
                        "type": "agent.text.delta",
                        "invocation_id": invocation_id,
                        "delta": "\n\n" + final_text,
                    }
                    break
                raise PersonalAgentChatError(
                    "the live model turn exceeded its bounded execution time"
                ) from exc
            prompt_count, output_count = _usage(event)
            if prompt_count is not None:
                input_tokens = max(input_tokens or 0, prompt_count)
            if output_count is not None:
                output_tokens = max(output_tokens or 0, output_count)
            if event.error_code or event.error_message:
                if completed_tools:
                    recovered_model_error = str(
                        event.error_code or "MODEL_RESPONSE_INTERRUPTED"
                    )
                    completion_mode = "AUTHORITATIVE_TOOL_RECOVERY"
                    final_text = authoritative_tool_recovery_message(completed_tools)
                    yield {
                        "type": "agent.text.delta",
                        "invocation_id": invocation_id,
                        "delta": "\n\n" + final_text,
                    }
                    break
                raise PersonalAgentChatError(
                    event.error_message or event.error_code or "model error"
                )
            if not event.content:
                continue
            for part in event.content.parts or []:
                if part.function_call:
                    call_id = str(part.function_call.id or f"tool_{uuid4().hex}")
                    if call_id not in tool_call_ids:
                        tool_call_ids.append(call_id)
                        yield {
                            "type": "tool.started",
                            "invocation_id": invocation_id,
                            "tool_call_id": call_id,
                            "tool_name": part.function_call.name,
                            "arguments": dict(part.function_call.args or {}),
                        }
                if part.function_response:
                    call_id = str(part.function_response.id or "")
                    response = part.function_response.response
                    completed_tools.append(
                        {
                            "name": str(part.function_response.name or ""),
                            "result": response,
                        }
                    )
                    if isinstance(response, dict):
                        directive_id = response.get("presentation_directive_id")
                        if directive_id and str(directive_id) not in directive_ids:
                            directive_ids.append(str(directive_id))
                            yield {
                                "type": "ui.directive",
                                "invocation_id": invocation_id,
                                "directive_id": str(directive_id),
                            }
                    yield {
                        "type": "tool.completed",
                        "invocation_id": invocation_id,
                        "tool_call_id": call_id,
                        "tool_name": part.function_response.name,
                        "result": response,
                    }
                if part.text and not getattr(part, "thought", False):
                    if event.partial:
                        partial_fragments.append(part.text)
                        yield {
                            "type": "agent.text.delta",
                            "invocation_id": invocation_id,
                            "delta": part.text,
                        }
                    elif event.author == "pairpilot_personal_agent":
                        final_text = part.text
                        if not partial_fragments:
                            yield {
                                "type": "agent.text.delta",
                                "invocation_id": invocation_id,
                                "delta": part.text,
                            }
        if not final_text:
            final_text = "".join(partial_fragments).strip()
        if not final_text:
            raise PersonalAgentChatError(
                "Agent completed without a user-visible response"
            )
        completed = datetime.now(UTC)
        latency_ms = int((time.monotonic() - started_clock) * 1000)
        message = {
            "schema_version": 2,
            "namespace": PRODUCTION_NAMESPACE,
            "message_id": assistant_message_id,
            "assistant_message_id": assistant_message_id,
            "owner_uid": principal.uid,
            "personal_agent_id": agent_id,
            "conversation_id": conversation_id,
            "task_id": task_id,
            "role": "PERSONAL_AGENT",
            "author_id": agent_id,
            "content": final_text,
            "visibility": "PRIVATE_USER_AGENT",
            "message_classification": (
                "FRESH_LIVE_GEMINI_RESPONSE"
                if completion_mode == "LIVE_MODEL"
                else "AUTHORITATIVE_TOOL_RECOVERY"
            ),
            "adk_session_id": session_id,
            "adk_invocation_id": invocation_id,
            "model_id": settings.model_id,
            "execution_mode": settings.execution_mode,
            "started_at": started,
            "completed_at": completed,
            "latency_ms": latency_ms,
            "input_token_count": input_tokens,
            "output_token_count": output_tokens,
            "tool_call_ids": tool_call_ids,
            "presentation_directive_ids": directive_ids,
            "error_status": None,
            "completion_mode": completion_mode,
            "recovered_model_error": recovered_model_error,
            "created_at": completed,
        }
        await store.create("conversation_messages", assistant_message_id, message)
        invocation.update(
            status="COMPLETED",
            completed_at=completed,
            latency_ms=latency_ms,
            input_token_count=input_tokens,
            output_token_count=output_tokens,
            tool_call_ids=tool_call_ids,
            presentation_directive_ids=directive_ids,
            completion_mode=completion_mode,
            recovered_model_error=recovered_model_error,
        )
        await store.upsert("agent_invocations", invocation_id, invocation)
        yield {
            "type": "agent.completed",
            "invocation_id": invocation_id,
            "assistant_message_id": assistant_message_id,
            "message": message,
        }
    except Exception as exc:
        logger.exception(
            "personal_agent_turn_failed",
            extra={
                "invocation_id": invocation_id,
                "conversation_id": conversation_id,
                "task_id": task_id,
                "owner_uid": principal.uid,
                "model_id": settings.model_id,
                "error_type": type(exc).__name__,
            },
        )
        completed = datetime.now(UTC)
        invocation.update(
            status="FAILED",
            completed_at=completed,
            latency_ms=int((time.monotonic() - started_clock) * 1000),
            input_token_count=input_tokens,
            output_token_count=output_tokens,
            tool_call_ids=tool_call_ids,
            presentation_directive_ids=directive_ids,
            error_status=type(exc).__name__,
        )
        await store.upsert("agent_invocations", invocation_id, invocation)
        yield {
            "type": "agent.error",
            "invocation_id": invocation_id,
            "error": "The live Personal Agent turn failed. Retry when ready.",
            "error_type": type(exc).__name__,
        }
    finally:
        if lease is not None:
            await release_execution_lease(store, lease)
