"""Public demo API and static frontend for the PairPilot golden path."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from time import monotonic
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pairpilot_schemas import (
    AdminModerationInput,
    AdminQuotaUpdateInput,
    AutonomyMode,
    AutonomyPolicyUpdateInput,
    BlockUserInput,
    CancelMatchInput,
    CommunityAgentQueryInput,
    CommunityModerationInput,
    CompleteMatchInput,
    ConnectionUsageInput,
    ContactCardInput,
    ConversationRole,
    CreateUserTaskInput,
    DecisionResolutionInput,
    DeleteAccountInput,
    ExploreSearchInput,
    FailedJobActionInput,
    FieldSource,
    HumanProposalDecisionInput,
    IntentPost,
    IntentPublicConstraints,
    IntentStatus,
    JoinCommunityInput,
    MatchChangeDecisionInput,
    MatchChangeProposalInput,
    MemoryActionInput,
    MessageAuthorship,
    MessageVisibility,
    NegotiationBoundaries,
    NotificationSettingsV2Input,
    OnboardingInput,
    OutcomeCheckInInput,
    PersonalAgentIntent,
    PresentationAction,
    PresentationMode,
    PublishUserPostInput,
    ReportInput,
    RoomChannelMessageInput,
    RoomMessage,
    SavePostInput,
    SaveSearchInput,
    SaveUserPostDraftInput,
    SpeakerType,
    UpdateAccountSettingsInput,
    UserRoomMessageInput,
)
from pydantic import BaseModel, ConfigDict, Field

from pairpilot_orchestrator.auth import (
    AuthenticatedPrincipal,
    require_authenticated_user,
    require_internal_worker,
    require_task_owner,
)
from pairpilot_orchestrator.auth.firebase_auth import (
    public_firebase_config,
    revoke_user_sessions,
)
from pairpilot_orchestrator.config import LIVE_MODE, Settings, runtime_environment
from pairpilot_orchestrator.domain import (
    AuthorityError,
    commit_approved_match,
    create_human_approval,
)
from pairpilot_orchestrator.generic_agent_runtime import (
    AgentRuntimeError,
    create_negotiation_for_pair,
)
from pairpilot_orchestrator.infrastructure import GoogleCloudStore
from pairpilot_orchestrator.intent_drafting import draft_with_qi_agent
from pairpilot_orchestrator.multi_user_commit import (
    MultiUserCommitError,
    approve_multi_user_proposal,
)
from pairpilot_orchestrator.multi_user_platform import (
    PRODUCTION_NAMESPACE,
    block_agent_owner,
    build_user_bootstrap,
    close_user_task,
    complete_onboarding,
    create_user_report,
    create_user_task,
    export_account_data,
    leave_user_room,
    provision_user,
    publish_user_post,
    save_user_post_draft,
    schedule_account_deletion,
    send_user_room_message,
    set_user_post_status,
    stable_id,
    update_account_settings,
)
from pairpilot_orchestrator.personal_agent_chat import stream_personal_agent_turn
from pairpilot_orchestrator.personal_agent_os import (
    GLOBAL_CONVERSATION_ID,
    build_os_bootstrap,
    create_presentation_directive,
    create_task_workspace,
    find_task_by_intent,
    materialize_task_run,
    public_task_summary,
    update_task_after_publish,
    write_conversation_message,
)
from pairpilot_orchestrator.personal_agent_routing import route_personal_agent_message
from pairpilot_orchestrator.policies.privacy import OutboundPrivacyGuard
from pairpilot_orchestrator.run_golden_path import run
from pairpilot_orchestrator.v1_candidate_pool import (
    process_candidate_pool_event,
    set_candidate_state,
)
from pairpilot_orchestrator.v1_foundation import (
    join_community,
    leave_community,
    list_communities_for_user,
)
from pairpilot_orchestrator.v1_reconciliation import (
    reconcile_candidate_availability,
    run_v1_reconciliation,
)
from pairpilot_orchestrator.v1_relationships import (
    list_match_contact_cards,
    offer_contact_card,
    revoke_contact_card,
    submit_outcome_check_in,
)
from pairpilot_orchestrator.v2_communities import (
    get_community_detail,
    query_community_agent,
)
from pairpilot_orchestrator.v2_connections import (
    get_connection_detail,
    list_connections_for_user,
    record_connection_usage,
    set_connection_preference,
)
from pairpilot_orchestrator.v2_marketplace import (
    create_saved_search,
    evaluate_saved_search,
    evaluate_saved_searches_for_post,
    get_post_detail,
    save_post,
    search_marketplace,
    unsave_post,
)
from pairpilot_orchestrator.v2_matches import (
    accept_contact_card,
    activate_backup,
    approve_match_change,
    build_match_calendar,
    cancel_match,
    get_match_detail,
    list_matches_for_user,
    mark_match_completed,
    propose_match_change,
)
from pairpilot_orchestrator.v2_memory import (
    apply_memory_action,
    get_memory_detail,
    list_memory_workspace,
)
from pairpilot_orchestrator.v2_operations import (
    build_operations_console,
    get_admin_report,
    list_community_reports,
    moderate_report,
    operate_failed_job,
    update_user_quota,
)
from pairpilot_orchestrator.v2_product_glue import (
    get_autonomy_center,
    list_decision_inbox,
    list_notifications,
    mark_all_notifications_read,
    resolve_decision,
    set_notification_state,
    update_autonomy_policy,
    update_notification_settings,
)
from pairpilot_orchestrator.v2_rooms import (
    get_room_workspace,
    list_rooms_for_user,
    send_room_channel_message,
    set_room_muted,
)

logger = logging.getLogger(__name__)

MAX_PUBLIC_RUNS_PER_UTC_DAY = 12
MAX_REQUESTS_PER_MINUTE = 120
POLL_SECONDS = 1.5
PUBLIC_COLLECTIONS = (
    "runs",
    "intents",
    "intent_pair_sessions",
    "agent_turns",
    "agent_messages",
    "beliefs",
    "proposals",
    "holds",
    "approval_requests",
    "approvals",
    "matches",
    "relationships",
    "relationship_events",
    "memories",
)

app = FastAPI(
    title="PairPilot — The Relationship Layer for Personal Agents",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)
_run_lock = asyncio.Lock()
_requests: defaultdict[str, deque[float]] = defaultdict(deque)


class ApprovalBody(BaseModel):
    """An explicit authorization for one visible proposal version."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    proposal_id: str
    proposal_version: int
    confirmation: str


class RejectBody(BaseModel):
    """A rejection for one visible proposal version."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    proposal_id: str
    proposal_version: int


class DraftIntentBody(BaseModel):
    """One raw owner need; it is never published directly."""

    model_config = ConfigDict(extra="forbid")

    raw_goal: str = Field(min_length=20, max_length=2_000)


class PublishIntentBody(BaseModel):
    """User-confirmed editable fields for one draft."""

    model_config = ConfigDict(extra="forbid")

    intent_id: str
    public_title: str = Field(min_length=1, max_length=120)
    public_summary: str = Field(min_length=1, max_length=600)
    event: str = Field(min_length=1, max_length=80)
    location: str = Field(min_length=1, max_length=120)
    date_start: date
    date_end: date
    roommate_gender_preference: str = Field(min_length=1, max_length=40)
    public_requirements: list[str] = Field(default_factory=list, max_length=12)
    quiet_overnight_compatibility_importance: str = Field(
        pattern=r"^(low|medium|high)$"
    )
    maximum_additional_cost_usd: int = Field(ge=0, le=10_000)
    partial_date_overlap_allowed: bool


class RevalidateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    proposal_id: str
    proposal_version: int


class PostStatusBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["OPEN", "PAUSED", "CLOSED"]


class CandidateStateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal["BACKUP", "WITHDRAWN", "PROMISING", "NEEDS_INFORMATION"]


class PubSubPushMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    data: str
    attributes: dict[str, str] = Field(default_factory=dict)


class PubSubPushBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: PubSubPushMessage
    subscription: str | None = None


class PersonalAgentMessageBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=2, max_length=4_000)
    task_id: str | None = None


class RoomModeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: AutonomyMode


class RoomActionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal[
        "TELL_QI_PRIVATELY",
        "ASK_QI_TO_DRAFT",
        "ASK_QI_TO_SEND",
        "SEND_AS_MYSELF",
    ]
    content: str = Field(min_length=1, max_length=4_000)


class MemoryActionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["CONFIRM", "CORRECT", "ARCHIVE", "DELETE", "RESTRICT_SCOPE"]
    content: str | None = Field(default=None, max_length=1_000)
    scope: str | None = Field(default=None, max_length=120)


class ConversationMessageBody(BaseModel):
    """One idempotent user turn sent to a persistent Personal Agent session."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=4_000)
    client_message_id: str = Field(min_length=8, max_length=100)
    task_id: str | None = Field(default=None, min_length=1, max_length=160)
    retry_of: str | None = Field(default=None, min_length=8, max_length=100)


def _store() -> GoogleCloudStore:
    settings = Settings.from_environment()
    return GoogleCloudStore(
        project_id=settings.project_id,
        topic_id=settings.event_topic_id,
        collection_prefix=settings.collection_prefix,
        environment=settings.environment,
    )


def _clean(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if not key.startswith("_")}


def _public_intent(item: dict[str, Any]) -> dict[str, Any]:
    """Return the registry projection; never owner-only matching notes."""

    return {
        "intent_id": item.get("intent_id") or item.get("_id"),
        "owner_agent_id": item.get("owner_agent_id"),
        "intent_type": item.get("intent_type"),
        "public_title": item.get("public_title"),
        "public_summary": item.get("public_summary"),
        "public_constraints": item.get("public_constraints"),
        "public_requirements": item.get("public_requirements", []),
        "capacity": item.get("capacity"),
        "capacity_remaining": item.get("capacity_remaining"),
        "status": item.get("status"),
        "version": item.get("version"),
        "task_id": item.get("task_id"),
        "authorship": item.get("authorship"),
        "demo_data": item.get("demo_data", item.get("owner_agent_id") != "qi-agent"),
        "created_at": item.get("created_at"),
        "published_at": item.get("published_at"),
        "expires_at": item.get("expires_at"),
    }


def _for_run(items: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    return [_clean(item) for item in items if item.get("runId") == run_id]


def _sort_time(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: str(
            item.get("createdAt")
            or item.get("receivedAt")
            or item.get("requestedAt")
            or item.get("startedAt")
            or ""
        ),
    )


async def public_state(run_id: str | None = None) -> dict[str, Any]:
    """Return observable demo state without any private profile contents."""

    store = _store()
    loaded = await asyncio.gather(
        *(store.list_documents(collection) for collection in PUBLIC_COLLECTIONS)
    )
    data = dict(zip(PUBLIC_COLLECTIONS, loaded, strict=True))
    raw_qi_intents = [
        item for item in data["intents"] if item.get("owner_agent_id") == "qi-agent"
    ]
    active_intent_raw = (
        max(
            raw_qi_intents,
            key=lambda item: str(
                item.get("created_at") or item.get("_updateTime") or ""
            ),
        )
        if raw_qi_intents
        else None
    )
    active_intent = _public_intent(active_intent_raw) if active_intent_raw else None
    active_intent_id = str(active_intent.get("intent_id")) if active_intent else ""
    runs = sorted(data["runs"], key=lambda item: str(item.get("startedAt", "")))
    selected = (
        next((item for item in runs if item.get("runId") == run_id), None)
        if run_id
        else next(
            (
                item
                for item in reversed(runs)
                if item.get("sourceIntentId") == active_intent_id
            ),
            None,
        )
    )
    selected_id = str(selected.get("runId")) if selected else ""
    turns = _sort_time(_for_run(data["agent_turns"], selected_id))
    messages = _sort_time(
        [
            {
                "messageId": item.get("message_id"),
                "fromAgentId": item.get("from_agent_id"),
                "toAgentId": item.get("to_agent_id"),
                "fromIntentId": item.get("from_intent_id"),
                "toIntentId": item.get("to_intent_id"),
                "pairSessionId": item.get("pair_session_id"),
                "speechAct": item.get("speech_act"),
                "naturalLanguage": item.get("natural_language"),
                "route": item.get("route"),
                "receivedAt": item.get("receivedAt"),
                "claimsAreAuthoritativeFacts": False,
            }
            for item in data["agent_messages"]
            if item.get("run_id") == selected_id
        ]
    )
    beliefs = [
        {
            "subjectAgentId": item.get("subject_agent_id")
            or item.get("subjectAgentId"),
            "field": item.get("field"),
            "value": item.get("value"),
            "kind": item.get("kind"),
            "observableReason": item.get("observableReason"),
            "authoritativeFact": False,
        }
        for item in data["beliefs"]
        if item.get("runId") == selected_id
    ]
    proposals = _for_run(data["proposals"], selected_id)
    holds = _for_run(data["holds"], selected_id)
    approval_requests = _for_run(data["approval_requests"], selected_id)
    approvals = _for_run(data["approvals"], selected_id)
    matches = _for_run(data["matches"], selected_id)
    intents = [_public_intent(item) for item in data["intents"]]
    now = datetime.now(UTC)
    for hold in holds:
        expires = datetime.fromisoformat(str(hold["expires_at"]).replace("Z", "+00:00"))
        hold["expired"] = expires <= now
    return {
        "product": "PairPilot",
        "executionMode": LIVE_MODE,
        "exactModelId": "gemini-3.7-flash",
        "activeIntent": active_intent,
        "intentRegistry": [
            item
            for item in intents
            if item.get("owner_agent_id") != "qi-agent"
            and item.get("status") == IntentStatus.OPEN.value
        ],
        "peerIntents": [
            item for item in intents if item.get("owner_agent_id") != "qi-agent"
        ],
        "intentPairSessions": [_clean(item) for item in data["intent_pair_sessions"]],
        "run": _clean(selected) if selected else None,
        "turns": turns,
        "messages": messages,
        "beliefs": beliefs,
        "proposals": proposals,
        "holds": holds,
        "approvalRequests": approval_requests,
        "approvals": approvals,
        "matches": matches,
        "relationships": [_clean(item) for item in data["relationships"]],
        "relationshipEvents": [_clean(item) for item in data["relationship_events"]],
        "memories": _for_run(data["memories"], selected_id),
        "protectedMemoryCount": 1,
        "limits": {
            "maximumGlobalTurns": 12,
            "maximumMessagesPerPair": 4,
            "maximumActiveCandidates": 2,
            "maximumWallClockSeconds": 90,
            "publicRunsPerUtcDay": MAX_PUBLIC_RUNS_PER_UTC_DAY,
        },
    }


async def _check_run_quota() -> None:
    today = datetime.now(UTC).date().isoformat()
    store = _store()
    quota = await store.get("demo_quota", today)
    count = int(quota.get("count", 0)) if quota else 0
    if count >= MAX_PUBLIC_RUNS_PER_UTC_DAY:
        raise HTTPException(429, "The safe public demo quota is exhausted for today.")
    await store.upsert(
        "demo_quota",
        today,
        {
            "date": today,
            "count": count + 1,
            "maximum": MAX_PUBLIC_RUNS_PER_UTC_DAY,
            "updatedAt": datetime.now(UTC),
        },
    )


def _sse(event: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, default=str, separators=(",", ":"))
    return f"event: {event}\ndata: {encoded}\n\n"


async def _owned_conversation(
    conversation_id: str, principal: AuthenticatedPrincipal
) -> dict[str, Any]:
    conversation = await _store().get("conversations", conversation_id)
    if conversation is None or conversation.get("namespace") != PRODUCTION_NAMESPACE:
        raise HTTPException(404, "Conversation was not found.")
    if conversation.get("owner_uid") != principal.uid:
        raise HTTPException(403, "Conversation belongs to another user.")
    return conversation


async def _persist_chat_event(
    store: Any,
    *,
    request_id: str,
    invocation_id: str,
    owner_uid: str,
    conversation_id: str,
    sequence: int,
    event: dict[str, Any],
) -> None:
    event_type = str(event["type"])
    await store.create(
        "chat_stream_events",
        stable_id("chat_event", invocation_id, str(sequence)),
        {
            "namespace": PRODUCTION_NAMESPACE,
            "request_id": request_id,
            "invocation_id": invocation_id,
            "owner_uid": owner_uid,
            "conversation_id": conversation_id,
            "sequence": sequence,
            "event_type": event_type,
            "payload": event,
            "created_at": datetime.now(UTC),
        },
    )
    if event_type == "tool.started":
        tool_call_id = str(event["tool_call_id"])
        await store.create(
            "agent_tool_calls",
            tool_call_id,
            {
                "namespace": PRODUCTION_NAMESPACE,
                "tool_call_id": tool_call_id,
                "owner_uid": owner_uid,
                "conversation_id": conversation_id,
                "invocation_id": invocation_id,
                "tool_name": event.get("tool_name"),
                "arguments": event.get("arguments", {}),
                "status": "RUNNING",
                "started_at": datetime.now(UTC),
            },
        )
    elif event_type == "tool.completed":
        tool_call_id = str(event["tool_call_id"])
        existing = await store.get("agent_tool_calls", tool_call_id) or {}
        await store.upsert(
            "agent_tool_calls",
            tool_call_id,
            {
                **_clean(existing),
                "namespace": PRODUCTION_NAMESPACE,
                "tool_call_id": tool_call_id,
                "owner_uid": owner_uid,
                "conversation_id": conversation_id,
                "invocation_id": invocation_id,
                "tool_name": event.get("tool_name"),
                "result": event.get("result"),
                "status": "COMPLETED",
                "completed_at": datetime.now(UTC),
            },
        )


async def _execute_personal_agent_request(
    *,
    request_id: str,
    invocation_id: str,
    principal: AuthenticatedPrincipal,
    conversation: dict[str, Any],
    body: ConversationMessageBody,
) -> None:
    """Run independently of the HTTP stream so reconnects can replay progress."""

    store = _store()
    sequence = 0
    terminal = False
    runner = getattr(app.state, "personal_agent_turn_runner", None)
    runner = runner or stream_personal_agent_turn
    stream = runner(
        store,
        principal,
        conversation=conversation,
        content=body.content,
        client_message_id=body.client_message_id,
        invocation_id=invocation_id,
    )
    try:
        async for event in stream:
            current = await store.get("chat_message_requests", request_id)
            if current and current.get("cancellation_requested") is True:
                await stream.aclose()
                event = {
                    "type": "agent.error",
                    "invocation_id": invocation_id,
                    "error": "This Agent turn was stopped by the user.",
                    "error_type": "AgentTurnCancelled",
                }
            sequence += 1
            await _persist_chat_event(
                store,
                request_id=request_id,
                invocation_id=invocation_id,
                owner_uid=principal.uid,
                conversation_id=str(conversation["conversation_id"]),
                sequence=sequence,
                event=event,
            )
            if event["type"] in {"agent.completed", "agent.error"}:
                terminal = True
                await store.upsert(
                    "chat_message_requests",
                    request_id,
                    {
                        **_clean(current or {}),
                        "namespace": PRODUCTION_NAMESPACE,
                        "request_id": request_id,
                        "invocation_id": invocation_id,
                        "owner_uid": principal.uid,
                        "conversation_id": conversation["conversation_id"],
                        "client_message_id": body.client_message_id,
                        "status": (
                            "COMPLETED"
                            if event["type"] == "agent.completed"
                            else "FAILED"
                        ),
                        "terminal_event_type": event["type"],
                        "updated_at": datetime.now(UTC),
                    },
                )
                break
    except Exception as exc:
        logger.exception(
            "personal_agent_request_failed",
            extra={
                "request_id": request_id,
                "invocation_id": invocation_id,
                "conversation_id": str(conversation["conversation_id"]),
                "owner_uid": principal.uid,
                "error_type": type(exc).__name__,
            },
        )
        sequence += 1
        event = {
            "type": "agent.error",
            "invocation_id": invocation_id,
            "error": "The live Personal Agent turn failed. Retry when ready.",
            "error_type": type(exc).__name__,
        }
        await _persist_chat_event(
            store,
            request_id=request_id,
            invocation_id=invocation_id,
            owner_uid=principal.uid,
            conversation_id=str(conversation["conversation_id"]),
            sequence=sequence,
            event=event,
        )
    finally:
        if not terminal:
            current = await store.get("chat_message_requests", request_id) or {}
            await store.upsert(
                "chat_message_requests",
                request_id,
                {
                    **_clean(current),
                    "namespace": PRODUCTION_NAMESPACE,
                    "request_id": request_id,
                    "invocation_id": invocation_id,
                    "owner_uid": principal.uid,
                    "conversation_id": conversation["conversation_id"],
                    "client_message_id": body.client_message_id,
                    "status": "FAILED",
                    "terminal_event_type": "agent.error",
                    "updated_at": datetime.now(UTC),
                },
            )


def _track_personal_agent_task(task: asyncio.Task[None]) -> None:
    tasks = getattr(app.state, "personal_agent_tasks", None)
    if tasks is None:
        tasks = set()
        app.state.personal_agent_tasks = tasks
    tasks.add(task)
    task.add_done_callback(tasks.discard)


async def _tail_personal_agent_events(
    *,
    request_id: str,
    invocation_id: str,
    owner_uid: str,
    after: int = 0,
) -> AsyncIterator[str]:
    next_sequence = after + 1
    deadline = monotonic() + 300
    while monotonic() < deadline:
        store = _store()
        events = await store.query_documents(
            "chat_stream_events",
            filters=[("invocation_id", "EQUAL", invocation_id)],
            limit=100,
        )
        for event in sorted(events, key=lambda item: int(item.get("sequence", 0))):
            sequence = int(event.get("sequence", 0))
            if sequence < next_sequence or event.get("owner_uid") != owner_uid:
                continue
            payload = dict(event.get("payload", {}))
            yield f"id: {sequence}\n" + _sse(str(event["event_type"]), payload)
            next_sequence = sequence + 1
        request = await store.get("chat_message_requests", request_id)
        if request is None or request.get("owner_uid") != owner_uid:
            return
        if request.get("status") in {"COMPLETED", "FAILED"}:
            return
        yield ": keep-alive\n\n"
        await asyncio.sleep(0.35)


async def _run_stream(run_id: UUID, source_intent_id: str) -> AsyncIterator[str]:
    task = asyncio.create_task(run(run_id=run_id, source_intent_id=source_intent_id))
    previous = ""
    try:
        yield _sse("started", {"runId": str(run_id)})
        while not task.done():
            snapshot = await public_state(str(run_id))
            encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
            if encoded != previous:
                previous = encoded
                yield _sse("snapshot", snapshot)
            await asyncio.sleep(POLL_SECONDS)
        result = await task
        final_state = await public_state(str(run_id))
        task_workspace = await find_task_by_intent(_store(), source_intent_id)
        if task_workspace is not None:
            await materialize_task_run(_store(), task=task_workspace, state=final_state)
        yield _sse("snapshot", final_state)
        yield _sse("complete", result)
    except asyncio.CancelledError:
        await asyncio.shield(task)
        raise
    finally:
        _run_lock.release()


@app.middleware("http")
async def rate_limit(request: Request, call_next: Any) -> Any:
    """Apply a small per-instance abuse bound to public API traffic."""

    if runtime_environment() != "production" and request.url.path.startswith(
        ("/api/demo", "/api/os", "/api/intents")
    ):
        return JSONResponse(
            {"detail": "Legacy demo surface is disabled."}, status_code=404
        )
    if request.url.path.startswith("/api/"):
        forwarded = request.headers.get("x-forwarded-for", "")
        client = forwarded.split(",", 1)[0].strip() or (
            request.client.host if request.client else "unknown"
        )
        now = monotonic()
        bucket = _requests[client]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= MAX_REQUESTS_PER_MINUTE:
            return JSONResponse(
                {"detail": "Request rate limit exceeded."}, status_code=429
            )
        bucket.append(now)
    return await call_next(request)


@app.get("/api/health")
async def health() -> dict[str, str]:
    settings = Settings.from_environment()
    return {
        "status": "ok",
        "service": "pairpilot-orchestrator",
        "executionMode": settings.execution_mode,
        "exactModelId": settings.model_id,
        "environment": settings.environment,
    }


@app.get("/api/auth/config")
async def auth_config() -> dict[str, Any]:
    """Expose only Firebase's non-secret browser application configuration."""

    config = public_firebase_config()
    return {
        "provider": "firebase",
        "emailPasswordEnabled": True,
        "emailVerificationRequiredForSocialActions": True,
        "firebaseConfigured": all(config.values()),
        "firebase": config,
    }


AuthenticatedUser = Annotated[
    AuthenticatedPrincipal, Depends(require_authenticated_user)
]


@app.post("/api/app/provision")
async def app_provision(principal: AuthenticatedUser) -> dict[str, Any]:
    profile = await provision_user(_store(), principal)
    return {"profile": profile}


@app.get("/api/app/bootstrap")
async def app_bootstrap(principal: AuthenticatedUser) -> dict[str, Any]:
    return await build_user_bootstrap(_store(), principal)


@app.get("/api/admin/dashboard")
async def admin_dashboard(principal: AuthenticatedUser) -> dict[str, Any]:
    return await build_operations_console(_store(), principal)


@app.get("/api/admin/reports/{report_id}")
async def admin_report_detail(
    report_id: str, principal: AuthenticatedUser
) -> dict[str, Any]:
    try:
        return await get_admin_report(_store(), principal, report_id)
    except LookupError as exc:
        raise HTTPException(404, "Report was not found.") from exc


@app.post("/api/admin/reports/{report_id}/actions")
async def admin_moderate_report(
    report_id: str,
    body: AdminModerationInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await moderate_report(
            _store(),
            principal,
            report_id=report_id,
            action=body.action,
            reason=body.reason,
        )
    except LookupError as exc:
        raise HTTPException(404, "Report or target was not found.") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/admin/failed-jobs/{job_id}/actions")
async def admin_failed_job_action(
    job_id: str,
    body: FailedJobActionInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await operate_failed_job(
            _store(),
            principal,
            job_id=job_id,
            action=body.action,
            idempotency_key=body.idempotency_key,
            reason=body.reason,
        )
    except LookupError as exc:
        raise HTTPException(404, "Failed job was not found.") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.put("/api/admin/quotas/{owner_uid}")
async def admin_update_quota(
    owner_uid: str,
    body: AdminQuotaUpdateInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await update_user_quota(
            _store(),
            principal,
            owner_uid=owner_uid,
            values={
                "active_task_limit": body.active_task_limit,
                "concurrent_negotiations_per_task": (
                    body.concurrent_negotiations_per_task
                ),
                "new_contacts_per_task": body.new_contacts_per_task,
                "daily_agent_turn_limit": body.daily_agent_turn_limit,
            },
            reason=body.reason,
        )
    except LookupError as exc:
        raise HTTPException(404, "Usage quota was not found.") from exc


@app.post("/api/v1/conversations/{conversation_id}/messages")
async def send_personal_agent_message(
    conversation_id: str,
    body: ConversationMessageBody,
    principal: AuthenticatedUser,
) -> StreamingResponse:
    """Accept one user turn and stream its durable Personal Agent execution."""

    conversation = await _owned_conversation(conversation_id, principal)
    raw_conversation_task_id = conversation.get("task_id")
    conversation_task_id = (
        str(raw_conversation_task_id)
        if raw_conversation_task_id not in (None, "")
        else None
    )
    if (
        body.task_id is not None
        and conversation_task_id is not None
        and body.task_id != conversation_task_id
    ):
        raise HTTPException(409, "The message task does not match this conversation.")
    effective_task_id = body.task_id or conversation_task_id
    if effective_task_id is not None:
        task_workspace = await _store().get("task_workspaces", effective_task_id)
        if task_workspace is None:
            raise HTTPException(404, "Task was not found.")
        require_task_owner(principal, task_workspace)
    effective_conversation = {
        **conversation,
        "task_id": effective_task_id,
    }
    request_id = stable_id(
        "chat_request", principal.uid, conversation_id, body.client_message_id
    )
    invocation_id = stable_id("invocation", request_id)
    store = _store()
    now = datetime.now(UTC)
    created = await store.create(
        "chat_message_requests",
        request_id,
        {
            "namespace": PRODUCTION_NAMESPACE,
            "request_id": request_id,
            "invocation_id": invocation_id,
            "owner_uid": principal.uid,
            "conversation_id": conversation_id,
            "task_id": effective_task_id,
            "client_message_id": body.client_message_id,
            "retry_of": body.retry_of,
            "status": "ACCEPTED",
            "cancellation_requested": False,
            "created_at": now,
            "updated_at": now,
        },
    )
    if created:
        user_message_id = stable_id("user_message", request_id)
        await store.create(
            "conversation_messages",
            user_message_id,
            {
                "schema_version": 2,
                "namespace": PRODUCTION_NAMESPACE,
                "message_id": user_message_id,
                "owner_uid": principal.uid,
                "personal_agent_id": conversation.get("principal_agent_id"),
                "conversation_id": conversation_id,
                "task_id": effective_task_id,
                "role": "USER",
                "author_id": principal.uid,
                "content": body.content,
                "visibility": "PRIVATE_USER_AGENT",
                "message_classification": "MANUALLY_ENTERED_USER_CONTENT",
                "client_message_id": body.client_message_id,
                "retry_of": body.retry_of,
                "created_at": now,
            },
        )
        task = asyncio.create_task(
            _execute_personal_agent_request(
                request_id=request_id,
                invocation_id=invocation_id,
                principal=principal,
                conversation=effective_conversation,
                body=body,
            )
        )
        _track_personal_agent_task(task)
    return StreamingResponse(
        _tail_personal_agent_events(
            request_id=request_id,
            invocation_id=invocation_id,
            owner_uid=principal.uid,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "X-PairPilot-Invocation-Id": invocation_id,
        },
    )


@app.get("/api/v1/conversations/{conversation_id}/events")
async def replay_personal_agent_events(
    conversation_id: str,
    invocation_id: str,
    principal: AuthenticatedUser,
    after: int = 0,
) -> StreamingResponse:
    await _owned_conversation(conversation_id, principal)
    requests = await _store().query_documents(
        "chat_message_requests",
        filters=[("invocation_id", "EQUAL", invocation_id)],
        limit=2,
    )
    matching = next(
        (
            item
            for item in requests
            if item.get("owner_uid") == principal.uid
            and item.get("conversation_id") == conversation_id
        ),
        None,
    )
    if matching is None:
        raise HTTPException(404, "Agent invocation was not found.")
    request_id = str(matching["request_id"])
    return StreamingResponse(
        _tail_personal_agent_events(
            request_id=request_id,
            invocation_id=invocation_id,
            owner_uid=principal.uid,
            after=max(after, 0),
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform"},
    )


@app.post("/api/v1/invocations/{invocation_id}/stop")
async def stop_personal_agent_invocation(
    invocation_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    requests = await _store().query_documents(
        "chat_message_requests",
        filters=[("invocation_id", "EQUAL", invocation_id)],
        limit=2,
    )
    request = next(
        (item for item in requests if item.get("owner_uid") == principal.uid), None
    )
    if request is None:
        raise HTTPException(404, "Agent invocation was not found.")
    if request.get("status") in {"COMPLETED", "FAILED"}:
        return {"status": request["status"], "invocationId": invocation_id}
    await _store().upsert(
        "chat_message_requests",
        str(request["request_id"]),
        {
            **_clean(request),
            "cancellation_requested": True,
            "updated_at": datetime.now(UTC),
        },
    )
    return {"status": "STOPPING", "invocationId": invocation_id}


@app.get("/api/v1/conversations/{conversation_id}/audit")
async def personal_agent_conversation_audit(
    conversation_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    """Return owner-visible provenance without hidden model reasoning."""

    conversation = await _owned_conversation(conversation_id, principal)
    store = _store()
    collections = {
        "messages": "conversation_messages",
        "invocations": "agent_invocations",
        "toolCalls": "agent_tool_calls",
        "directives": "presentation_directives",
    }
    result: dict[str, Any] = {}
    for response_key, collection in collections.items():
        items = await store.query_documents(
            collection,
            filters=[("conversation_id", "EQUAL", conversation_id)],
            limit=100,
        )
        result[response_key] = [
            _clean(item) for item in items if item.get("owner_uid") == principal.uid
        ]
    task_id = str(conversation.get("task_id", ""))
    task = await store.get("task_workspaces", task_id) if task_id else None
    if task is not None:
        a2a_turns = await store.query_documents(
            "a2a_agent_turns",
            filters=[("owner_uid", "EQUAL", principal.uid)],
            limit=100,
        )
        result["a2aTurns"] = [
            _clean(item)
            for item in a2a_turns
            if item.get("own_intent_id") == task.get("intent_id")
        ]
    else:
        result["a2aTurns"] = []
    return result


@app.get("/api/app/matches")
async def app_list_matches(
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    return await list_matches_for_user(_store(), principal)


@app.get("/api/app/decisions")
async def app_list_decisions(principal: AuthenticatedUser) -> dict[str, Any]:
    return await list_decision_inbox(_store(), principal)


@app.post("/api/app/decisions/{decision_id}/resolve")
async def app_resolve_decision(
    decision_id: str,
    body: DecisionResolutionInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        decision = await resolve_decision(
            _store(),
            principal,
            decision_id=decision_id,
            outcome=body.outcome,
            confirmation=body.confirmation,
        )
    except LookupError as exc:
        raise HTTPException(404, "Decision was not found.") from exc
    except PermissionError as exc:
        raise HTTPException(403, "Decision is not owned by this account.") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"decision": decision}


@app.get("/api/app/notifications")
async def app_list_notifications(principal: AuthenticatedUser) -> dict[str, Any]:
    return await list_notifications(_store(), principal)


@app.put("/api/app/notifications/read-all")
async def app_read_all_notifications(
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    return await mark_all_notifications_read(_store(), principal)


@app.put("/api/app/notifications/{notification_id}/read")
async def app_read_notification(
    notification_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        notification = await set_notification_state(
            _store(), principal, notification_id=notification_id, state="READ"
        )
    except LookupError as exc:
        raise HTTPException(404, "Notification was not found.") from exc
    return {"notification": notification}


@app.put("/api/app/notifications/{notification_id}/archived")
async def app_archive_notification(
    notification_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        notification = await set_notification_state(
            _store(), principal, notification_id=notification_id, state="ARCHIVED"
        )
    except LookupError as exc:
        raise HTTPException(404, "Notification was not found.") from exc
    return {"notification": notification}


@app.put("/api/app/notification-settings")
async def app_update_notification_settings_v2(
    body: NotificationSettingsV2Input,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    settings = await update_notification_settings(
        _store(), principal, values=body.model_dump()
    )
    return {"settings": settings}


@app.get("/api/app/autonomy")
async def app_get_autonomy(principal: AuthenticatedUser) -> dict[str, Any]:
    return await get_autonomy_center(_store(), principal)


@app.put("/api/app/autonomy")
async def app_update_autonomy(
    body: AutonomyPolicyUpdateInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await update_autonomy_policy(
            _store(),
            principal,
            action_levels=body.action_levels,
            task_id=body.task_id,
        )
    except LookupError as exc:
        raise HTTPException(404, "Task was not found.") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/app/connections")
async def app_list_connections(
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    return await list_connections_for_user(_store(), principal)


@app.get("/api/app/connections/{connection_id}")
async def app_get_connection(
    connection_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await get_connection_detail(_store(), principal, connection_id)
    except LookupError as exc:
        raise HTTPException(404, "Connection was not found.") from exc


@app.put("/api/app/connections/{connection_id}/muted")
async def app_mute_connection(
    connection_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await set_connection_preference(
            _store(), principal, connection_id=connection_id, muted=True
        )
    except LookupError as exc:
        raise HTTPException(404, "Connection was not found.") from exc


@app.delete("/api/app/connections/{connection_id}/muted")
async def app_unmute_connection(
    connection_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await set_connection_preference(
            _store(), principal, connection_id=connection_id, muted=False
        )
    except LookupError as exc:
        raise HTTPException(404, "Connection was not found.") from exc


@app.put("/api/app/connections/{connection_id}/suggestions/removed")
async def app_remove_connection_from_suggestions(
    connection_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await set_connection_preference(
            _store(),
            principal,
            connection_id=connection_id,
            removed_from_suggestions=True,
        )
    except LookupError as exc:
        raise HTTPException(404, "Connection was not found.") from exc


@app.post("/api/app/connections/{connection_id}/usage")
async def app_record_connection_usage(
    connection_id: str,
    body: ConnectionUsageInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        usage = await record_connection_usage(
            _store(),
            principal,
            connection_id=connection_id,
            task_id=body.task_id,
            purpose=body.purpose,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"usage": usage}


@app.get("/api/app/matches/{match_id}")
async def app_get_match_detail(
    match_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await get_match_detail(_store(), principal, match_id)
    except LookupError as exc:
        raise HTTPException(404, "Match was not found.") from exc


@app.get("/api/app/matches/{match_id}/calendar.ics")
async def app_download_match_calendar(
    match_id: str,
    principal: AuthenticatedUser,
) -> Response:
    try:
        calendar = await build_match_calendar(_store(), principal, match_id)
    except LookupError as exc:
        raise HTTPException(404, "Match was not found.") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return Response(
        content=calendar,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="pairpilot-{match_id}.ics"'
        },
    )


@app.post("/api/app/matches/{match_id}/changes")
async def app_propose_match_change(
    match_id: str,
    body: MatchChangeProposalInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        change = await propose_match_change(
            _store(),
            principal,
            match_id=match_id,
            summary=body.summary,
            terms=body.terms,
        )
    except LookupError as exc:
        raise HTTPException(404, "Match was not found.") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"changeProposal": change}


@app.post("/api/app/matches/{match_id}/changes/{change_id}/approve")
async def app_approve_match_change(
    match_id: str,
    change_id: str,
    body: MatchChangeDecisionInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await approve_match_change(
            _store(),
            principal,
            match_id=match_id,
            change_id=change_id,
            version=body.version,
            confirmation=body.confirmation,
        )
    except LookupError as exc:
        raise HTTPException(404, "Match change was not found.") from exc
    except PermissionError as exc:
        raise HTTPException(403, "This change is not assigned to you.") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/app/matches/{match_id}/cancel")
async def app_cancel_match(
    match_id: str,
    body: CancelMatchInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        match = await cancel_match(
            _store(),
            principal,
            match_id=match_id,
            reason=body.reason,
            reopen_candidate_pool=body.reopen_candidate_pool,
        )
    except LookupError as exc:
        raise HTTPException(404, "Match was not found.") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"match": match}


@app.post("/api/app/matches/{match_id}/backup/activate")
async def app_activate_match_backup(
    match_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await activate_backup(_store(), principal, match_id=match_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/app/matches/{match_id}/complete")
async def app_complete_match(
    match_id: str,
    _body: CompleteMatchInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        match = await mark_match_completed(_store(), principal, match_id=match_id)
    except LookupError as exc:
        raise HTTPException(404, "Match was not found.") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"match": match}


@app.post("/api/app/matches/{match_id}/contacts/{contact_card_id}/accept")
async def app_accept_match_contact(
    match_id: str,
    contact_card_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        acceptance = await accept_contact_card(
            _store(),
            principal,
            match_id=match_id,
            contact_card_id=contact_card_id,
        )
    except LookupError as exc:
        raise HTTPException(404, "Contact card was not found.") from exc
    return {"acceptance": acceptance}


@app.get("/api/app/matches/{match_id}/contacts")
async def app_list_match_contacts(
    match_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        cards = await list_match_contact_cards(_store(), principal, match_id=match_id)
    except LookupError as exc:
        raise HTTPException(404, "Match was not found.") from exc
    return {"contactCards": cards}


@app.put("/api/app/matches/{match_id}/contacts/mine")
async def app_offer_match_contact(
    match_id: str,
    body: ContactCardInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        card = await offer_contact_card(
            _store(), principal, match_id=match_id, body=body
        )
    except LookupError as exc:
        raise HTTPException(404, "Match was not found.") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"contactCard": card}


@app.delete("/api/app/matches/{match_id}/contacts/mine")
async def app_revoke_match_contact(
    match_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        card = await revoke_contact_card(_store(), principal, match_id=match_id)
    except LookupError as exc:
        raise HTTPException(404, "Contact card was not found.") from exc
    return {"contactCard": card}


@app.post("/api/app/matches/{match_id}/outcome")
async def app_submit_match_outcome(
    match_id: str,
    body: OutcomeCheckInInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        outcome = await submit_outcome_check_in(
            _store(), principal, match_id=match_id, body=body
        )
    except LookupError as exc:
        raise HTTPException(404, "Match was not found.") from exc
    return {"outcome": outcome}


@app.put("/api/app/onboarding")
async def app_onboarding(
    body: OnboardingInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    profile = await complete_onboarding(_store(), principal, body)
    return {"profile": profile}


@app.get("/api/app/communities")
async def app_list_communities(
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    return await list_communities_for_user(_store(), principal)


@app.get("/api/app/communities/{community_id}")
async def app_get_community_detail(
    community_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await get_community_detail(_store(), principal, community_id)
    except LookupError as exc:
        raise HTTPException(404, "Community was not found.") from exc


@app.post("/api/app/communities/{community_id}/agent/query")
async def app_query_community_agent(
    community_id: str,
    body: CommunityAgentQueryInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await query_community_agent(
            _store(), principal, community_id, body.question
        )
    except LookupError as exc:
        raise HTTPException(404, "Community was not found.") from exc


@app.get("/api/app/communities/{community_id}/moderation/reports")
async def app_list_community_moderation_reports(
    community_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    return await list_community_reports(_store(), principal, community_id)


@app.post("/api/app/communities/{community_id}/moderation/reports/{report_id}/actions")
async def app_moderate_community_report(
    community_id: str,
    report_id: str,
    body: CommunityModerationInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await moderate_report(
            _store(),
            principal,
            report_id=report_id,
            action=body.action,
            reason=body.reason,
            community_id=community_id,
        )
    except LookupError as exc:
        raise HTTPException(404, "Report or target was not found.") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/app/explore/search")
async def app_search_marketplace(
    body: ExploreSearchInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await search_marketplace(_store(), principal, body)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/app/posts/{intent_id}")
async def app_get_post_detail(
    intent_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await get_post_detail(_store(), principal, intent_id)
    except LookupError as exc:
        raise HTTPException(404, "Post was not found.") from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


@app.put("/api/app/posts/{intent_id}/saved")
async def app_save_post(
    intent_id: str,
    body: SavePostInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        saved = await save_post(
            _store(), principal, intent_id=intent_id, task_id=body.task_id
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    return {"savedPost": saved}


@app.delete("/api/app/posts/{intent_id}/saved")
async def app_unsave_post(
    intent_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    return {"savedPost": await unsave_post(_store(), principal, intent_id=intent_id)}


@app.post("/api/app/saved-searches")
async def app_create_saved_search(
    body: SaveSearchInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        saved_search = await create_saved_search(_store(), principal, body)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"savedSearch": saved_search}


@app.post("/api/app/communities/{community_id}/join")
async def app_join_community(
    community_id: str,
    body: JoinCommunityInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        membership = await join_community(
            _store(), principal, community_id, invite_token=body.invite_token
        )
    except LookupError as exc:
        raise HTTPException(404, "Community was not found.") from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    return {"membership": membership}


@app.post("/api/app/communities/{community_id}/leave")
async def app_leave_community(
    community_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        membership = await leave_community(_store(), principal, community_id)
    except LookupError as exc:
        raise HTTPException(404, "Community membership was not found.") from exc
    return {"membership": membership}


@app.get("/api/app/memories")
async def app_list_memories(principal: AuthenticatedUser) -> dict[str, Any]:
    return await list_memory_workspace(_store(), principal)


@app.get("/api/app/memories/{memory_id}")
async def app_get_memory(
    memory_id: str, principal: AuthenticatedUser
) -> dict[str, Any]:
    try:
        return await get_memory_detail(_store(), principal, memory_id)
    except LookupError as exc:
        raise HTTPException(404, "Memory was not found.") from exc


@app.post("/api/app/memories/{memory_id}/actions")
async def app_memory_action(
    memory_id: str,
    body: MemoryActionInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        memory = await apply_memory_action(
            _store(),
            principal,
            memory_id=memory_id,
            action=body.action,
            content=body.content,
            scope=body.scope,
        )
    except LookupError as exc:
        raise HTTPException(404, "Memory was not found.") from exc
    except PermissionError as exc:
        raise HTTPException(403, "Memory is not owned by this account.") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"memory": memory}


@app.post("/api/app/tasks")
async def app_create_task(
    body: CreateUserTaskInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        task = await create_user_task(_store(), principal, body)
    except PermissionError as exc:
        raise HTTPException(
            403,
            detail={
                "code": str(exc),
                "message": "Join the selected community before creating a request.",
            },
        ) from exc
    except ValueError as exc:
        if str(exc) == "ACTIVE_TASK_QUOTA_EXCEEDED":
            raise HTTPException(
                429,
                detail={
                    "code": "ACTIVE_TASK_QUOTA_EXCEEDED",
                    "message": "Close an active request before creating another.",
                },
            ) from exc
        if str(exc) == "UNSUPPORTED_INTENT_TYPE":
            raise HTTPException(422, "Unsupported PairPilot V1 intent type.") from exc
        raise
    return {"task": task}


@app.get("/api/app/tasks/{task_id}")
async def app_get_task(
    task_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    task = await _store().get("task_workspaces", task_id)
    if task is None or task.get("namespace") != PRODUCTION_NAMESPACE:
        raise HTTPException(404, "Task was not found.")
    require_task_owner(principal, task)
    private_intent = await _store().get("intent_private_data", str(task["intent_id"]))
    return {
        "task": {key: value for key, value in task.items() if not key.startswith("_")},
        "privateIntent": (
            {
                key: value
                for key, value in private_intent.items()
                if not key.startswith("_")
            }
            if private_intent is not None
            else None
        ),
    }


@app.post("/api/app/tasks/{task_id}/close")
async def app_close_task(
    task_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        task = await close_user_task(_store(), principal, task_id=task_id)
    except LookupError as exc:
        raise HTTPException(404, "Task was not found.") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"task": task, "status": "CANCELLED"}


@app.post("/api/app/tasks/{task_id}/publish")
async def app_publish_task(
    task_id: str,
    body: PublishUserPostInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        post = await publish_user_post(
            _store(),
            principal,
            task_id=task_id,
            public_title=body.public_title,
            public_summary=body.public_summary,
            public_requirements=body.public_requirements,
        )
    except LookupError as exc:
        raise HTTPException(404, "Task was not found.") from exc
    except PermissionError as exc:
        raise HTTPException(
            403,
            detail={"code": str(exc), "message": "Complete onboarding first."},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            422,
            detail={
                "code": "PUBLIC_DISCLOSURE_VIOLATION",
                "message": "Remove contact details or protected private information.",
            },
        ) from exc
    return {"post": post, "status": "PUBLISHED"}


@app.put("/api/app/tasks/{task_id}/draft")
async def app_save_task_draft(
    task_id: str,
    body: SaveUserPostDraftInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        draft = await save_user_post_draft(
            _store(),
            principal,
            task_id=task_id,
            public_title=body.public_title,
            public_summary=body.public_summary,
            public_requirements=body.public_requirements,
        )
    except LookupError as exc:
        raise HTTPException(404, "Task was not found.") from exc
    return {"draft": draft, "status": "SAVED"}


@app.post("/api/app/tasks/{task_id}/candidates/{candidate_intent_id}/contact")
async def app_contact_explore_candidate(
    task_id: str,
    candidate_intent_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    """Ask the owner's Agent to evaluate one explicitly selected public post."""

    store = _store()
    task = await store.get("task_workspaces", task_id)
    if task is None:
        raise HTTPException(404, "Task was not found.")
    require_task_owner(principal, task)
    source_intent_id = str(task.get("intent_id", ""))
    target = await store.get("intent_posts", candidate_intent_id)
    if target is None or target.get("status") != "OPEN":
        raise HTTPException(409, "This public post is no longer available.")
    if target.get("owner_uid") == principal.uid:
        raise HTTPException(422, "Your Agent cannot contact your own post.")
    try:
        result = await process_candidate_pool_event(
            store,
            source_intent_id,
            requested_target_id=candidate_intent_id,
        )
    except AgentRuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "CONTACTED", "result": result}


@app.patch("/api/app/posts/{intent_id}/status")
async def app_set_post_status(
    intent_id: str,
    body: PostStatusBody,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        post = await set_user_post_status(
            _store(), principal, intent_id=intent_id, status=body.status
        )
    except LookupError as exc:
        raise HTTPException(404, "Post was not found.") from exc
    return {"post": post}


@app.patch("/api/app/tasks/{task_id}/candidates/{candidate_intent_id}/state")
async def app_set_candidate_state(
    task_id: str,
    candidate_intent_id: str,
    body: CandidateStateBody,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        assessment = await set_candidate_state(
            _store(),
            owner_uid=principal.uid,
            task_id=task_id,
            candidate_intent_id=candidate_intent_id,
            state=body.state,
        )
    except LookupError as exc:
        raise HTTPException(404, "Candidate was not found.") from exc
    except PermissionError as exc:
        raise HTTPException(403, "Candidate is not owned by this account.") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"candidate": assessment}


@app.post("/api/app/tasks/{task_id}/candidates/{candidate_intent_id}/proposal")
async def app_create_candidate_proposal(
    task_id: str,
    candidate_intent_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    """Promote one ranked candidate into an exact two-human proposal."""

    store = _store()
    task = await store.get("task_workspaces", task_id)
    if task is None:
        raise HTTPException(404, "Task was not found.")
    require_task_owner(principal, task)
    source_intent_id = str(task.get("intent_id", ""))
    source_post, target_post = await asyncio.gather(
        store.get("intent_posts", source_intent_id),
        store.get("intent_posts", candidate_intent_id),
    )
    if source_post is None or target_post is None:
        raise HTTPException(409, "One of the candidate posts is no longer available.")
    assessment_id = stable_id("candidate", task_id, candidate_intent_id)
    assessment = await store.get("candidate_assessments", assessment_id)
    if assessment is None or assessment.get("owner_uid") != principal.uid:
        raise HTTPException(404, "Candidate was not found in this task.")
    room_messages = await store.query_documents(
        "room_messages", filters=[("room_id", "EQUAL", assessment.get("room_id"))]
    )
    agent_messages = {
        str(item["speaker_id"]): str(item["content"])
        for item in room_messages
        if item.get("speaker_type") == "PERSONAL_AGENT"
    }
    try:
        proposal = await create_negotiation_for_pair(
            store,
            source_post=source_post,
            target_post=target_post,
            agent_messages=agent_messages,
        )
    except AgentRuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    clean_assessment = _clean(assessment)
    clean_assessment.update(
        state="RECOMMENDED",
        proposal_id=proposal["proposal_id"],
        updated_at=datetime.now(UTC),
    )
    await store.upsert("candidate_assessments", assessment_id, clean_assessment)
    return {"proposal": proposal, "candidate": clean_assessment}


@app.post("/api/app/proposals/{proposal_id}/approve")
async def app_approve_proposal(
    proposal_id: str,
    body: HumanProposalDecisionInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        result = await approve_multi_user_proposal(
            _store(),
            principal,
            proposal_id=proposal_id,
            proposal_version=body.proposal_version,
            confirmation=body.confirmation,
        )
    except PermissionError as exc:
        raise HTTPException(
            403,
            detail={"code": "FORBIDDEN", "message": "You cannot approve this."},
        ) from exc
    except MultiUserCommitError as exc:
        raise HTTPException(
            409,
            detail={"code": "APPROVAL_PRECONDITION_FAILED", "message": str(exc)},
        ) from exc
    if "match" in result:
        result["match"] = {
            key: value
            for key, value in dict(result["match"]).items()
            if key not in {"participant_uids"}
        }
    return result


@app.get("/api/app/rooms")
async def app_list_rooms(
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    return await list_rooms_for_user(_store(), principal)


@app.get("/api/app/rooms/{room_id}")
async def app_get_room(
    room_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await get_room_workspace(_store(), principal, room_id)
    except LookupError as exc:
        raise HTTPException(404, "Room was not found.") from exc


@app.post("/api/app/rooms/{room_id}/messages")
async def app_send_room_message(
    room_id: str,
    body: UserRoomMessageInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        message = await send_user_room_message(
            _store(),
            principal,
            room_id=room_id,
            content=body.content,
            authorship=body.authorship,
            idempotency_key=body.idempotency_key,
        )
    except LookupError as exc:
        raise HTTPException(404, "Room was not found.") from exc
    except PermissionError as exc:
        raise HTTPException(
            403,
            detail={"code": str(exc), "message": "The shared room is locked."},
        ) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"message": message}


@app.post("/api/app/rooms/{room_id}/channels/{channel}/messages")
async def app_send_room_channel_message(
    room_id: str,
    channel: Literal["PRIVATE_USER_AGENT", "AGENTS_ONLY", "SHARED_ROOM"],
    body: RoomChannelMessageInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        message = await send_room_channel_message(
            _store(),
            principal,
            room_id=room_id,
            channel=channel,
            content=body.content,
            authorship=body.authorship,
            idempotency_key=body.idempotency_key,
            reply_to=body.reply_to,
        )
    except LookupError as exc:
        raise HTTPException(404, "Room was not found.") from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"message": message}


@app.put("/api/app/rooms/{room_id}/muted")
async def app_mute_room(
    room_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return {
            "preference": await set_room_muted(
                _store(), principal, room_id=room_id, muted=True
            )
        }
    except LookupError as exc:
        raise HTTPException(404, "Room was not found.") from exc


@app.delete("/api/app/rooms/{room_id}/muted")
async def app_unmute_room(
    room_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return {
            "preference": await set_room_muted(
                _store(), principal, room_id=room_id, muted=False
            )
        }
    except LookupError as exc:
        raise HTTPException(404, "Room was not found.") from exc


@app.post("/api/app/blocks")
async def app_block_user(
    body: BlockUserInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await block_agent_owner(
            _store(),
            principal,
            target_agent_id=body.target_agent_id,
            reason=body.reason,
        )
    except LookupError as exc:
        raise HTTPException(404, "Target was not found.") from exc


@app.post("/api/app/reports")
async def app_report(
    body: ReportInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    return await create_user_report(
        _store(),
        principal,
        target_type=body.target_type,
        target_id=body.target_id,
        category=body.category,
        details=body.details,
    )


@app.put("/api/app/settings")
async def app_update_settings(
    body: UpdateAccountSettingsInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await update_account_settings(_store(), principal, body)
    except LookupError as exc:
        raise HTTPException(404, "Account settings were not found.") from exc


@app.get("/api/app/account/export")
async def app_export_account(principal: AuthenticatedUser) -> dict[str, Any]:
    return await export_account_data(_store(), principal)


@app.post("/api/app/rooms/{room_id}/leave")
async def app_leave_room(
    room_id: str,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        return await leave_user_room(_store(), principal, room_id)
    except LookupError as exc:
        raise HTTPException(404, "Room was not found.") from exc


@app.post("/api/app/account/delete")
async def app_delete_account(
    _body: DeleteAccountInput,
    principal: AuthenticatedUser,
) -> dict[str, Any]:
    try:
        result = await schedule_account_deletion(_store(), principal)
    except LookupError as exc:
        raise HTTPException(404, "Account was not found.") from exc
    await revoke_user_sessions(principal.uid)
    return result


InternalWorker = Annotated[str, Depends(require_internal_worker)]


@app.post("/api/internal/events")
async def internal_event_worker(
    body: PubSubPushBody,
    _worker: InternalWorker,
) -> dict[str, Any]:
    """Consume one authenticated Pub/Sub push as one bounded Agent turn."""

    try:
        event = json.loads(base64.b64decode(body.message.data).decode())
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(400, "Invalid Pub/Sub event payload.") from exc
    event_type = str(event.get("eventType", ""))
    availability_events = {
        "intent.closed.v1",
        "intent.paused.v1",
        "intent.open.v1",
        "intent.expired.v1",
        "intent.matched.v1",
    }
    saved_search_event = "marketplace.saved_search.created.v2"
    if event_type not in {
        "intent.published.v2",
        "agent.contact.requested.v3",
        "proposal.evaluation.requested.v3",
        saved_search_event,
        *availability_events,
    }:
        return {"status": "IGNORED"}
    if event_type in availability_events:
        changed = await reconcile_candidate_availability(
            _store(), now=datetime.now(UTC)
        )
        return {"status": "AVAILABILITY_RECONCILED", "changed": changed}
    event_payload = dict(event.get("payload", {}))
    if event_type == saved_search_event:
        saved_search_id = str(event_payload.get("savedSearchId") or "")
        if not saved_search_id:
            raise HTTPException(400, "Saved-search event is missing savedSearchId.")
        result = await evaluate_saved_search(_store(), saved_search_id)
        return {"status": "SAVED_SEARCH_EVALUATED", "result": result}
    intent_id = str(
        event_payload.get("intentId") or event_payload.get("sourceIntentId") or ""
    )
    requested_target_id = str(event_payload.get("targetIntentId", ""))
    if not intent_id:
        raise HTTPException(400, "Published intent event is missing intentId.")
    try:
        store = _store()
        monitored = (
            await evaluate_saved_searches_for_post(store, intent_id)
            if event_type == "intent.published.v2"
            else {"searches_evaluated": 0, "new_matches": 0}
        )
        result = await process_candidate_pool_event(
            store,
            intent_id,
            requested_target_id=requested_target_id or None,
        )
    except AgentRuntimeError as exc:
        return {"status": "NO_ACTION", "reason": str(exc)}
    return {"status": "PROCESSED", "result": result, "monitored": monitored}


@app.post("/api/internal/reconcile")
async def internal_reconcile_worker(
    _worker: InternalWorker,
) -> dict[str, Any]:
    """Repair missed events and stale state without browser participation."""

    return await run_v1_reconciliation(_store())


@app.get("/api/demo/state")
async def state(run_id: str | None = None) -> dict[str, Any]:
    return await public_state(run_id)


@app.post("/api/intents/draft")
async def draft_intent(body: DraftIntentBody) -> dict[str, Any]:
    """Ask live Qi Agent for a typed draft, then store it without publishing."""

    store = _store()
    existing_qi_intents = [
        item
        for item in await store.list_documents("intents")
        if item.get("owner_agent_id") == "qi-agent"
        and item.get("status")
        not in {
            IntentStatus.MATCHED.value,
            IntentStatus.CLOSED.value,
            IntentStatus.EXPIRED.value,
            IntentStatus.CANCELLED.value,
        }
    ]
    if len(existing_qi_intents) >= 5:
        raise HTTPException(
            409, "The public demo supports at most five simultaneous active requests."
        )
    try:
        async with asyncio.timeout(60):
            draft = await draft_with_qi_agent(body.raw_goal)
    except TimeoutError as exc:
        raise HTTPException(
            504, "Qi Agent drafting exceeded the safe time bound."
        ) from exc
    now = datetime.now(UTC)
    intent_id = f"intent_qi_{uuid4().hex[:16]}"
    post = IntentPost(
        intent_id=intent_id,
        owner_agent_id="qi-agent",
        intent_type=draft.intent_type,
        raw_user_goal_ref=f"intent-private://{intent_id}",
        public_title=draft.public_title,
        public_summary=draft.public_summary,
        public_constraints=IntentPublicConstraints(
            event=draft.event,
            location=draft.location,
            date_start=draft.date_start,
            date_end=draft.date_end,
            roommate_gender_preference=draft.roommate_gender_preference,
        ),
        public_requirements=draft.public_requirements,
        negotiation_boundaries=NegotiationBoundaries(
            partial_date_overlap_allowed=(
                draft.agent_only.partial_date_overlap_allowed
            ),
            maximum_additional_cost_usd=(draft.agent_only.maximum_additional_cost_usd),
        ),
        capacity=1,
        capacity_remaining=1,
        status=IntentStatus.DRAFT,
        version=1,
        field_provenance=draft.field_provenance.model_dump(),
        created_at=now,
        expires_at=now + timedelta(days=7),
        provenance={"source": "user_goal_and_qi_agent_draft"},
    )
    created = await store.create("intents", intent_id, post.model_dump(mode="json"))
    if not created:
        raise HTTPException(409, "Draft identifier already exists.")
    await store.create(
        "intent_private",
        intent_id,
        {
            "intent_id": intent_id,
            "owner_agent_id": "qi-agent",
            "raw_user_goal": body.raw_goal,
            "agent_only_constraints": {
                "quiet_overnight_compatibility": {
                    "importance": (
                        draft.agent_only.quiet_overnight_compatibility_importance
                    ),
                    "source": (
                        draft.field_provenance.quiet_overnight_compatibility.value
                    ),
                },
                "maximum_additional_cost_usd": (
                    draft.agent_only.maximum_additional_cost_usd
                ),
                "partial_date_overlap_allowed": (
                    draft.agent_only.partial_date_overlap_allowed
                ),
            },
            "protected_memory_refs": ["private-sleep-memory-reference"],
            "protected_fact_count": 1,
            "readable_by": ["qi-agent"],
            "uncertainties": draft.uncertainties,
        },
    )
    await store.write_event(
        event_type="intent.drafted",
        run_id=f"draft:{intent_id}",
        producer="qi-agent",
        payload={"intentId": intent_id, "status": IntentStatus.DRAFT.value},
        idempotency_key=f"intent.drafted:{intent_id}:v1",
    )
    return await _intent_review(store, intent_id)


async def _intent_review(store: GoogleCloudStore, intent_id: str) -> dict[str, Any]:
    post, private = await asyncio.gather(
        store.get("intents", intent_id),
        store.get("intent_private", intent_id),
    )
    if post is None or private is None or post.get("owner_agent_id") != "qi-agent":
        raise HTTPException(404, "Qi intent draft was not found.")
    return {
        "publicPost": _public_intent(post),
        "agentOnly": private.get("agent_only_constraints", {}),
        "protected": {
            "count": int(private.get("protected_fact_count", 0)),
            "summary": "Protected sleep-related fact",
            "disclosure": "Never included in public posts or peer-agent messages",
        },
        "fieldProvenance": post.get("field_provenance", {}),
        "uncertainties": private.get("uncertainties", []),
    }


@app.get("/api/intents/{intent_id}/review")
async def intent_review(intent_id: str) -> dict[str, Any]:
    return await _intent_review(_store(), intent_id)


@app.get("/api/os/bootstrap")
async def os_bootstrap() -> dict[str, Any]:
    """Return the routed product shell from authoritative, redacted records."""

    store = _store()
    return await build_os_bootstrap(store, demo_state=await public_state())


async def _directive_entities(
    store: GoogleCloudStore,
    *,
    task: dict[str, Any],
    action: PresentationAction,
) -> list[str]:
    task_id = str(task["task_id"])
    intent_id = str(task["intent_id"])
    if action in {PresentationAction.OPEN_TASK, PresentationAction.SHOW_TASK_STATUS}:
        return [task_id]
    if action == PresentationAction.SHOW_POST:
        return [intent_id]
    if action in {
        PresentationAction.SHOW_RELATED_POSTS,
        PresentationAction.SHOW_CANDIDATE_COMPARISON,
    }:
        assessments = [
            item
            for item in await store.list_documents("candidate_assessments")
            if item.get("task_id") == task_id
        ]
        return [
            str(item.get("assessment_id") or item.get("_id")) for item in assessments
        ]
    if action == PresentationAction.OPEN_COORDINATION_ROOM:
        rooms = [
            item
            for item in await store.list_documents("coordination_rooms")
            if item.get("task_id") == task_id
        ]
        return [str(item.get("room_id") or item.get("_id")) for item in rooms[:1]]
    if action in {PresentationAction.SHOW_PROPOSAL, PresentationAction.SHOW_APPROVAL}:
        return [
            value
            for value in [
                str(task.get("active_proposal_id") or ""),
                *[str(item) for item in task.get("decision_ids", [])],
            ]
            if value
        ]
    if action in {
        PresentationAction.SHOW_NETWORK_PATH,
        PresentationAction.SHOW_RELATIONSHIP,
        PresentationAction.SHOW_MEMORY,
        PresentationAction.FILTER_EXPLORE,
    }:
        return [task_id]
    return [task_id, intent_id]


@app.post("/api/os/messages")
async def personal_agent_message(body: PersonalAgentMessageBody) -> dict[str, Any]:
    """Route one global or task message through the typed persistent Qi Agent."""

    store = _store()
    tasks = [_clean(item) for item in await store.list_documents("task_workspaces")]
    selected_task = next(
        (item for item in tasks if item.get("task_id") == body.task_id), None
    )
    if body.task_id and selected_task is None:
        raise HTTPException(404, "Task workspace was not found.")
    conversation_id = (
        str(selected_task["conversation_id"])
        if selected_task
        else GLOBAL_CONVERSATION_ID
    )
    await write_conversation_message(
        store,
        conversation_id=conversation_id,
        task_id=body.task_id,
        role=ConversationRole.USER,
        author_id="qi-owner",
        content=body.content,
    )
    try:
        async with asyncio.timeout(60):
            routing = await route_personal_agent_message(
                message=body.content,
                task_summaries=[public_task_summary(task) for task in tasks],
                current_task_id=body.task_id,
            )
    except TimeoutError as exc:
        raise HTTPException(
            504, "Qi Agent routing exceeded the safe time bound."
        ) from exc
    if routing.target_task_id and routing.target_task_id not in {
        str(item.get("task_id")) for item in tasks
    }:
        raise HTTPException(400, "Qi Agent referenced an unauthorized task.")
    if routing.intent == PersonalAgentIntent.NEW_TASK:
        if body.task_id:
            raise HTTPException(
                409, "A new request must begin with the global Qi Agent."
            )
        review = await draft_intent(DraftIntentBody(raw_goal=body.content))
        intent_id = str(review["publicPost"]["intent_id"])
        title = routing.suggested_title or str(review["publicPost"]["public_title"])
        task, decision = await create_task_workspace(
            store,
            intent_id=intent_id,
            raw_goal=body.content,
            title=title,
        )
        directive = await create_presentation_directive(
            store,
            action=PresentationAction.OPEN_TASK,
            explanation=(
                "Qi created an isolated request workspace and a reviewable post draft."
            ),
            task_id=str(task["task_id"]),
            entity_ids=[str(task["task_id"]), intent_id],
        )
        task_message = await write_conversation_message(
            store,
            conversation_id=str(task["conversation_id"]),
            task_id=str(task["task_id"]),
            role=ConversationRole.PERSONAL_AGENT,
            author_id="qi-agent",
            content=routing.response_text,
            directive_ids=[str(directive["directive_id"])],
        )
        global_message = await write_conversation_message(
            store,
            conversation_id=GLOBAL_CONVERSATION_ID,
            task_id=None,
            role=ConversationRole.PERSONAL_AGENT,
            author_id="qi-agent",
            content=routing.response_text,
            directive_ids=[str(directive["directive_id"])],
        )
        return {
            "routing": routing.model_dump(mode="json"),
            "task": task,
            "decision": decision,
            "review": review,
            "directive": directive,
            "message": global_message,
            "taskMessage": task_message,
        }
    target_task = selected_task or next(
        (item for item in tasks if item.get("task_id") == routing.target_task_id),
        None,
    )
    directive_payload: dict[str, Any] | None = None
    if target_task and routing.presentation_actions:
        action = routing.presentation_actions[0]
        entities = await _directive_entities(store, task=target_task, action=action)
        directive_payload = await create_presentation_directive(
            store,
            action=action,
            explanation=routing.response_text,
            task_id=str(target_task["task_id"]),
            entity_ids=entities,
            presentation=PresentationMode.INLINE_CARD,
        )
    response_message = await write_conversation_message(
        store,
        conversation_id=conversation_id,
        task_id=body.task_id,
        role=ConversationRole.PERSONAL_AGENT,
        author_id="qi-agent",
        content=routing.response_text,
        directive_ids=(
            [str(directive_payload["directive_id"])]
            if directive_payload is not None
            else []
        ),
    )
    return {
        "routing": routing.model_dump(mode="json"),
        "directive": directive_payload,
        "message": response_message,
    }


@app.get("/api/os/tasks/{task_id}")
async def task_workspace(task_id: str) -> dict[str, Any]:
    store = _store()
    task = await store.get("task_workspaces", task_id)
    if task is None or task.get("namespace") == "production":
        raise HTTPException(404, "Task workspace was not found.")
    collections = await build_os_bootstrap(store, demo_state=await public_state())
    return {
        "task": _clean(task),
        "messages": [
            item
            for item in collections["conversationMessages"]
            if item.get("task_id") == task_id
        ],
        "decisions": [
            item for item in collections["decisions"] if item.get("task_id") == task_id
        ],
        "assessments": [
            item
            for item in collections["candidateAssessments"]
            if item.get("task_id") == task_id
        ],
        "rooms": [
            item for item in collections["rooms"] if item.get("task_id") == task_id
        ],
        "demoState": collections["demoState"],
    }


@app.post("/api/os/rooms/{room_id}/mode")
async def change_room_mode(room_id: str, body: RoomModeBody) -> dict[str, Any]:
    store = _store()
    room = await store.get("coordination_rooms", room_id)
    if room is None or room.get("namespace") == "production":
        raise HTTPException(404, "Coordination Room was not found.")
    room.pop("_updateTime", None)
    room.update(autonomy_mode=body.mode.value, updated_at=datetime.now(UTC))
    await store.upsert("coordination_rooms", room_id, room)
    await store.write_event(
        event_type="room.mode.changed",
        run_id=str(room["task_id"]),
        producer="qi-owner",
        payload={"roomId": room_id, "mode": body.mode.value},
        idempotency_key=f"room.mode.changed:{room_id}:{body.mode.value}",
    )
    return _clean(room)


@app.post("/api/os/rooms/{room_id}/messages")
async def room_message(room_id: str, body: RoomActionBody) -> dict[str, Any]:
    """Keep private, agents-only and shared-room channels structurally separate."""

    store = _store()
    room = await store.get("coordination_rooms", room_id)
    if room is None or room.get("namespace") == "production":
        raise HTTPException(404, "Coordination Room was not found.")
    if body.action != "SEND_AS_MYSELF":
        task = await store.get("task_workspaces", str(room["task_id"]))
        if task is None:
            raise HTTPException(404, "Task workspace was not found.")
        private_message = await write_conversation_message(
            store,
            conversation_id=str(task["conversation_id"]),
            task_id=str(room["task_id"]),
            role=ConversationRole.USER,
            author_id="qi-owner",
            content=body.content,
        )
        room_entry = RoomMessage(
            message_id=f"room_message_{uuid4().hex}",
            room_id=room_id,
            task_id=str(room["task_id"]),
            source_intent_id=str(room["source_intent_id"]),
            target_intent_id=str(room["target_intent_id"]),
            speaker_id="qi-owner",
            speaker_type=SpeakerType.HUMAN,
            authorship=MessageAuthorship.HUMAN_WRITTEN,
            visibility=MessageVisibility.PRIVATE_USER_AGENT,
            content=body.content,
            provenance={"source": "explicit_room_action", "action": body.action},
        )
        await store.create(
            "room_messages",
            room_entry.message_id,
            room_entry.model_dump(mode="json"),
        )
        return {
            "channel": MessageVisibility.PRIVATE_USER_AGENT.value,
            "message": room_entry.model_dump(mode="json"),
            "conversationMessage": private_message,
        }
    if (
        room.get("room_type") != "SHARED_COORDINATION_ROOM"
        or room.get("human_participation_available") is not True
    ):
        raise HTTPException(409, "Human messages require an unlocked shared room.")
    visibility = MessageVisibility.SHARED_ROOM
    authorship = MessageAuthorship.HUMAN_WRITTEN
    speaker_id = "qi-owner"
    speaker_type = SpeakerType.HUMAN
    room_entry = RoomMessage(
        message_id=f"room_message_{uuid4().hex}",
        room_id=room_id,
        task_id=str(room["task_id"]),
        source_intent_id=str(room["source_intent_id"]),
        target_intent_id=str(room["target_intent_id"]),
        speaker_id=speaker_id,
        speaker_type=speaker_type,
        authorship=authorship,
        visibility=visibility,
        content=body.content,
        provenance={"source": "explicit_room_action", "action": body.action},
    )
    await store.create(
        "room_messages", room_entry.message_id, room_entry.model_dump(mode="json")
    )
    return {
        "channel": visibility.value,
        "message": room_entry.model_dump(mode="json"),
    }


@app.post("/api/os/memories/{memory_id}")
async def update_memory(memory_id: str, body: MemoryActionBody) -> dict[str, Any]:
    store = _store()
    memory = await store.get("memories", memory_id)
    if memory is None or memory.get("namespace") == "production":
        raise HTTPException(404, "Memory was not found.")
    memory.pop("_updateTime", None)
    now = datetime.now(UTC)
    if body.action == "DELETE":
        memory.update(confirmation_status="deleted", archived=True, updated_at=now)
    elif body.action == "ARCHIVE":
        memory.update(confirmation_status="archived", archived=True, updated_at=now)
    elif body.action == "CONFIRM":
        memory.update(confirmation_status="confirmed", last_confirmed_at=now)
    elif body.action == "CORRECT":
        if not body.content:
            raise HTTPException(400, "Corrected memory content is required.")
        memory.update(
            content=body.content,
            confirmation_status="confirmed_user_corrected",
            last_confirmed_at=now,
        )
    elif body.action == "RESTRICT_SCOPE":
        if not body.scope:
            raise HTTPException(400, "A restricted scope is required.")
        memory.update(scope=body.scope, use_for_matching=False, updated_at=now)
    await store.upsert("memories", memory_id, memory)
    return _clean(memory)


@app.post("/api/intents/publish")
async def publish_intent(body: PublishIntentBody) -> dict[str, Any]:
    """Apply owner edits and make one post authoritatively searchable."""

    if body.date_end <= body.date_start:
        raise HTTPException(400, "End date must follow start date.")
    privacy = OutboundPrivacyGuard()
    try:
        privacy.validate(
            natural_language="\n".join(
                [body.public_title, body.public_summary, *body.public_requirements]
            ),
            references=[],
        )
    except ValueError as exc:
        raise HTTPException(400, "Public post contains protected information.") from exc
    store = _store()
    current = await store.get("intents", body.intent_id)
    private = await store.get("intent_private", body.intent_id)
    if (
        current is None
        or private is None
        or current.get("owner_agent_id") != "qi-agent"
    ):
        raise HTTPException(404, "Qi intent draft was not found.")
    if current.get("status") == IntentStatus.OPEN.value:
        await update_task_after_publish(store, intent_id=body.intent_id)
        refreshed = await store.get("intents", body.intent_id)
        return {
            "status": "OPEN",
            "intent": _public_intent(refreshed or current),
            "created": False,
        }
    if current.get("status") not in {
        IntentStatus.DRAFT.value,
        IntentStatus.READY_FOR_REVIEW.value,
    }:
        raise HTTPException(409, "Only a reviewable draft can be published.")
    now = datetime.now(UTC)
    provenance = dict(current.get("field_provenance", {}))
    editable_values = {
        "public_title": body.public_title,
        "public_summary": body.public_summary,
        "event": body.event,
        "location": body.location,
        "date_start": body.date_start.isoformat(),
        "date_end": body.date_end.isoformat(),
        "roommate_gender_preference": body.roommate_gender_preference,
        "public_requirements": body.public_requirements,
        "maximum_additional_cost_usd": body.maximum_additional_cost_usd,
        "partial_date_overlap_allowed": body.partial_date_overlap_allowed,
    }
    current_constraints = dict(current.get("public_constraints", {}))
    current_boundaries = dict(current.get("negotiation_boundaries", {}))
    current_values = {
        "public_title": current.get("public_title"),
        "public_summary": current.get("public_summary"),
        "event": current_constraints.get("event"),
        "location": current_constraints.get("location"),
        "date_start": str(current_constraints.get("date_start")),
        "date_end": str(current_constraints.get("date_end")),
        "roommate_gender_preference": current_constraints.get(
            "roommate_gender_preference"
        ),
        "public_requirements": current.get("public_requirements", []),
        "maximum_additional_cost_usd": current_boundaries.get(
            "maximum_additional_cost_usd"
        ),
        "partial_date_overlap_allowed": current_boundaries.get(
            "partial_date_overlap_allowed"
        ),
    }
    for field, value in editable_values.items():
        if value != current_values[field]:
            provenance[field] = FieldSource.USER_EDIT.value
    post = IntentPost(
        intent_id=body.intent_id,
        owner_agent_id="qi-agent",
        intent_type=str(current["intent_type"]),
        raw_user_goal_ref=str(current["raw_user_goal_ref"]),
        public_title=body.public_title,
        public_summary=body.public_summary,
        public_constraints=IntentPublicConstraints(
            event=body.event,
            location=body.location,
            date_start=body.date_start,
            date_end=body.date_end,
            roommate_gender_preference=body.roommate_gender_preference,
        ),
        public_requirements=body.public_requirements,
        negotiation_boundaries=NegotiationBoundaries(
            partial_date_overlap_allowed=body.partial_date_overlap_allowed,
            maximum_additional_cost_usd=body.maximum_additional_cost_usd,
        ),
        capacity=int(current.get("capacity", 1)),
        capacity_remaining=int(current.get("capacity_remaining", 1)),
        status=IntentStatus.OPEN,
        version=int(current.get("version", 1)) + 1,
        field_provenance=provenance,
        created_at=datetime.fromisoformat(
            str(current["created_at"]).replace("Z", "+00:00")
        ),
        published_at=now,
        expires_at=now + timedelta(days=7),
        provenance={"source": "user_confirmed_qi_agent_draft"},
    )
    current_agent_only = dict(private.get("agent_only_constraints", {}))
    current_quiet = dict(current_agent_only.get("quiet_overnight_compatibility", {}))
    quiet_source = str(
        current_quiet.get("source", FieldSource.EXPLICIT_USER_INPUT.value)
    )
    if current_quiet.get("importance") != body.quiet_overnight_compatibility_importance:
        quiet_source = FieldSource.USER_EDIT.value
        provenance["quiet_overnight_compatibility"] = quiet_source
        post.field_provenance = provenance
    private.pop("_updateTime", None)
    private["agent_only_constraints"] = {
        "quiet_overnight_compatibility": {
            "importance": body.quiet_overnight_compatibility_importance,
            "source": quiet_source,
        },
        "maximum_additional_cost_usd": body.maximum_additional_cost_usd,
        "partial_date_overlap_allowed": body.partial_date_overlap_allowed,
    }
    await asyncio.gather(
        store.upsert("intents", body.intent_id, post.model_dump(mode="json")),
        store.upsert("intent_private", body.intent_id, private),
    )
    event = await store.write_event(
        event_type="intent.published",
        run_id=f"intent:{body.intent_id}",
        producer="qi-agent",
        payload={"intentId": body.intent_id, "version": post.version},
        idempotency_key=f"intent.published:{body.intent_id}",
    )
    await update_task_after_publish(store, intent_id=body.intent_id)
    published = await store.get("intents", body.intent_id)
    return {
        "status": "OPEN",
        "intent": _public_intent(published or post.model_dump(mode="json")),
        "created": event["created"],
    }


@app.get("/api/intents/open")
async def open_intents() -> dict[str, Any]:
    now = datetime.now(UTC)
    results = []
    for item in await _store().list_documents("intents"):
        expires = datetime.fromisoformat(
            str(item.get("expires_at", "1970-01-01T00:00:00Z")).replace("Z", "+00:00")
        )
        if (
            item.get("status") == IntentStatus.OPEN.value
            and int(item.get("capacity_remaining", 0)) > 0
            and expires > now
        ):
            results.append(_public_intent(item))
    return {"intents": results}


@app.get("/api/intents/{intent_id}")
async def public_intent(intent_id: str) -> dict[str, Any]:
    item = await _store().get("intents", intent_id)
    if item is None:
        raise HTTPException(404, "Intent was not found.")
    return _public_intent(item)


@app.get("/api/demo/run/stream")
async def start_run(intent_id: str) -> StreamingResponse:
    if _run_lock.locked():
        raise HTTPException(409, "A live public demo run is already active.")
    await _run_lock.acquire()
    try:
        intent = await _store().get("intents", intent_id)
        if (
            intent is None
            or intent.get("owner_agent_id") != "qi-agent"
            or intent.get("status") != IntentStatus.OPEN.value
        ):
            raise HTTPException(409, "Publish an OPEN Qi intent before starting.")
        await _check_run_quota()
    except Exception:
        _run_lock.release()
        raise
    run_id = uuid4()
    return StreamingResponse(
        _run_stream(run_id, intent_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/demo/reset")
async def reset_demo() -> dict[str, Any]:
    if _run_lock.locked():
        raise HTTPException(409, "Cannot reset while a run is active.")
    from infra.seed_demo import reset_workflow, seed

    project_id = Settings.from_environment().project_id
    deleted = await asyncio.to_thread(reset_workflow, project_id)
    seeded = await asyncio.to_thread(seed, project_id, dry_run=False)
    return {"status": "RESET", "deleted": deleted, "seeded": seeded}


@app.post("/api/demo/revalidate")
async def revalidate_offer(body: RevalidateBody) -> dict[str, Any]:
    """Explicitly renew an expired hold while the accepted proposal remains valid."""

    store = _store()
    request_id = f"{body.proposal_id}-v{body.proposal_version}"
    request = await store.get("approval_requests", request_id)
    proposal = await store.get("proposals", body.proposal_id)
    if (
        request is None
        or proposal is None
        or request.get("runId") != body.run_id
        or int(proposal.get("version", 0)) != body.proposal_version
    ):
        raise HTTPException(404, "Current offer was not found.")
    now = datetime.now(UTC)
    old_hold = await store.get("holds", str(request["holdId"]))
    if old_hold is not None:
        old_expiry = datetime.fromisoformat(
            str(old_hold["expires_at"]).replace("Z", "+00:00")
        )
        if old_hold.get("active") is True and old_expiry > now:
            return {
                "status": "STILL_ACTIVE",
                "holdId": old_hold["hold_id"],
                "holdExpiresAt": old_hold["expires_at"],
                "proposalVersion": body.proposal_version,
            }
    proposal_expiry = datetime.fromisoformat(
        str(proposal["expires_at"]).replace("Z", "+00:00")
    )
    if proposal_expiry <= now:
        raise HTTPException(
            409,
            "The proposal itself expired. Qi Agent must resume search; "
            "it was not revived.",
        )
    source_intent_id = str(proposal["source_intent_id"])
    target_intent_id = str(proposal["target_intent_id"])
    source_intent, target_intent = await asyncio.gather(
        store.get("intents", source_intent_id),
        store.get("intents", target_intent_id),
    )
    if any(item is None for item in (source_intent, target_intent)):
        raise HTTPException(409, "One of the intent posts no longer exists.")
    assert source_intent is not None
    assert target_intent is not None
    if any(
        item.get("status") != IntentStatus.AWAITING_APPROVAL.value
        or int(item.get("capacity_remaining", 0)) < 1
        for item in (source_intent, target_intent)
    ):
        raise HTTPException(409, "Both intent posts are no longer available.")
    candidate = str(proposal["candidate_agent_id"])
    acceptance_ids = (
        f"{body.proposal_id}-v{body.proposal_version}-qi-agent",
        f"{body.proposal_id}-v{body.proposal_version}-{candidate}",
    )
    acceptances = await asyncio.gather(
        *(store.get("proposal_acceptances", item) for item in acceptance_ids)
    )
    if any(item is None for item in acceptances):
        raise HTTPException(409, "Both agents no longer have a current acceptance.")
    renewal_count = int(request.get("renewalCount", 0)) + 1
    hold_key = (
        f"{proposal['pair_session_id']}:{body.proposal_id}:"
        f"v{body.proposal_version}:renewal:{renewal_count}"
    )
    hold_id = f"hold-{sha256(hold_key.encode()).hexdigest()[:24]}"
    expires_at = now + timedelta(minutes=15)
    hold = {
        "hold_id": hold_id,
        "proposal_id": body.proposal_id,
        "proposal_version": body.proposal_version,
        "source_intent_id": source_intent_id,
        "target_intent_id": target_intent_id,
        "pair_session_id": proposal["pair_session_id"],
        "candidate_agent_id": candidate,
        "capacity_reserved": 1,
        "status": "ACTIVE",
        "idempotency_key": hold_key,
        "expires_at": expires_at,
        "active": True,
        "runId": body.run_id,
    }
    created = await store.create("holds", hold_id, hold)
    if not created:
        existing = await store.get("holds", hold_id)
        if existing is None:
            raise HTTPException(409, "Renewed hold disappeared.")
        hold = existing
    if old_hold is not None:
        old_hold.pop("_updateTime", None)
        old_hold.update(
            active=False,
            status="EXPIRED",
            releasedAt=now,
            releaseReason="explicit_revalidation",
        )
        await store.upsert("holds", str(request["holdId"]), old_hold)
    request.pop("_updateTime", None)
    request.update(
        status="AWAITING_HUMAN",
        holdId=hold_id,
        holdExpiresAt=expires_at,
        renewalCount=renewal_count,
        revalidatedAt=now,
    )
    await store.upsert("approval_requests", request_id, request)
    await store.write_event(
        event_type="hold.revalidated",
        run_id=body.run_id,
        producer="commit-authority",
        payload={
            "holdId": hold_id,
            "proposalId": body.proposal_id,
            "proposalVersion": body.proposal_version,
            "sourceIntentId": source_intent_id,
            "targetIntentId": target_intent_id,
        },
        idempotency_key=hold_key,
    )
    task_workspace = await find_task_by_intent(store, source_intent_id)
    if task_workspace is not None:
        await materialize_task_run(
            store,
            task=task_workspace,
            state=await public_state(body.run_id),
        )
    return {
        "status": "REVALIDATED",
        "holdId": hold_id,
        "holdExpiresAt": expires_at,
        "proposalVersion": body.proposal_version,
    }


@app.post("/api/demo/approve")
async def approve(body: ApprovalBody) -> dict[str, Any]:
    required = f"APPROVE VERSION {body.proposal_version}"
    if body.confirmation != required:
        raise HTTPException(400, "Exact current-version approval is required.")
    store = _store()
    request_id = f"{body.proposal_id}-v{body.proposal_version}"
    approval_request = await store.get("approval_requests", request_id)
    if approval_request is None or approval_request.get("runId") != body.run_id:
        raise HTTPException(404, "Current approval request was not found.")
    existing_match, existing_approval = await asyncio.gather(
        store.get("matches", body.proposal_id),
        store.get("approvals", body.proposal_id),
    )
    if existing_match is not None:
        if (
            existing_approval is None
            or existing_match.get("runId") != body.run_id
            or int(existing_match.get("proposalVersion", 0)) != body.proposal_version
            or int(existing_approval.get("proposalVersion", 0)) != body.proposal_version
            or existing_approval.get("disclosureHash")
            != approval_request.get("disclosureHash")
        ):
            raise HTTPException(409, "Committed approval evidence is inconsistent.")
        source_intent_id = str(approval_request.get("sourceIntentId", ""))
        task_workspace = await find_task_by_intent(store, source_intent_id)
        if task_workspace is not None:
            await materialize_task_run(
                store,
                task=task_workspace,
                state=await public_state(body.run_id),
            )
        return {
            "status": "COMMITTED",
            "approval": _clean(existing_approval),
            "match": _clean(existing_match),
            "replayed": True,
        }
    try:
        approval = await create_human_approval(
            store=store,
            run_id=body.run_id,
            proposal_id=body.proposal_id,
            proposal_version=body.proposal_version,
            disclosure_hash=str(approval_request["disclosureHash"]),
        )
        match = await commit_approved_match(
            store=store,
            run_id=body.run_id,
            proposal_id=body.proposal_id,
        )
    except AuthorityError as exc:
        raise HTTPException(409, f"Commit blocked safely: {exc}") from exc
    source_intent_id = str(approval_request.get("sourceIntentId", ""))
    task_workspace = await find_task_by_intent(store, source_intent_id)
    if task_workspace is not None:
        await materialize_task_run(
            store,
            task=task_workspace,
            state=await public_state(body.run_id),
        )
    return {
        "status": "COMMITTED",
        "approval": approval,
        "match": match,
        "replayed": False,
    }


@app.post("/api/demo/reject")
async def reject(body: RejectBody) -> dict[str, str]:
    store = _store()
    request_id = f"{body.proposal_id}-v{body.proposal_version}"
    approval_request = await store.get("approval_requests", request_id)
    if approval_request is None or approval_request.get("runId") != body.run_id:
        raise HTTPException(404, "Current approval request was not found.")
    hold = await store.get("holds", str(approval_request["holdId"]))
    if hold:
        hold["active"] = False
        hold.pop("_updateTime", None)
        await store.upsert("holds", str(approval_request["holdId"]), hold)
    approval_request["status"] = "REJECTED"
    approval_request["rejectedAt"] = datetime.now(UTC)
    approval_request.pop("_updateTime", None)
    await store.upsert("approval_requests", request_id, approval_request)
    proposal = await store.get("proposals", body.proposal_id)
    if proposal is not None:
        for intent_id in (
            str(proposal.get("source_intent_id", "")),
            str(proposal.get("target_intent_id", "")),
        ):
            if not intent_id:
                continue
            intent = await store.get("intents", intent_id)
            if intent is not None and int(intent.get("capacity_remaining", 0)) > 0:
                intent.pop("_updateTime", None)
                intent["status"] = IntentStatus.OPEN.value
                intent.pop("active_hold_id", None)
                await store.upsert("intents", intent_id, intent)
        pair_session_id = str(proposal.get("pair_session_id", ""))
        session = await store.get("intent_pair_sessions", pair_session_id)
        if session is not None:
            session.pop("_updateTime", None)
            session.update(
                status="RELEASED",
                release_reason="human_rejected_effect",
                released_at=datetime.now(UTC),
            )
            await store.upsert("intent_pair_sessions", pair_session_id, session)
    await store.upsert(
        "runs",
        body.run_id,
        {
            "runId": body.run_id,
            "status": "USER_REJECTED",
            "updatedAt": datetime.now(UTC),
            "exactModelId": "gemini-3.7-flash",
            "executionMode": LIVE_MODE,
        },
    )
    return {"status": "USER_REJECTED"}


WEB_DIST = Path(os.environ.get("PAIRPILOT_WEB_DIST", "web/dist")).resolve()
if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/og.png", include_in_schema=False)
    async def social_card() -> FileResponse:
        return FileResponse(WEB_DIST / "og.png", media_type="image/png")

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(request: Request, path: str) -> HTMLResponse:
        origin = os.environ.get("PAIRPILOT_PUBLIC_BASE_URL", "").rstrip("/")
        if not origin:
            origin = str(request.base_url).rstrip("/")
        html = (
            (WEB_DIST / "index.html")
            .read_text()
            .replace("__PAIRPILOT_ORIGIN__", origin)
        )
        return HTMLResponse(html)
