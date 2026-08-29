"""Persistence and authoritative projections for the Personal Agent OS."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pairpilot_schemas import (
    AutonomyMode,
    CandidateAssessment,
    CandidatePriorityBand,
    Conversation,
    ConversationKind,
    ConversationMessage,
    ConversationRole,
    CoordinationRoom,
    DecisionInboxItem,
    DecisionStatus,
    DecisionType,
    MessageAuthorship,
    MessageVisibility,
    PresentationAction,
    PresentationDirective,
    PresentationMode,
    RoomMessage,
    RoomStatus,
    RoomType,
    SpeakerType,
    TaskStatus,
    TaskWorkspace,
)

from pairpilot_orchestrator.infrastructure import GoogleCloudStore

OS_COLLECTIONS = (
    "task_workspaces",
    "conversations",
    "conversation_messages",
    "candidate_assessments",
    "coordination_rooms",
    "room_messages",
    "presentation_directives",
    "decision_inbox",
    "internal_worker_runs",
)

GLOBAL_CONVERSATION_ID = "conversation_global_qi"
TASK_PRIORITY = {
    TaskStatus.NEEDS_DECISION.value: 0,
    TaskStatus.ACTIVE_NEGOTIATION.value: 1,
    TaskStatus.SEARCHING.value: 2,
    TaskStatus.DRAFT.value: 3,
    TaskStatus.COMPLETED.value: 4,
    TaskStatus.CANCELLED.value: 5,
}


def clean(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if not key.startswith("_")}


def public_task_summary(task: dict[str, Any]) -> dict[str, object]:
    """Expose only the bounded global context Qi needs for routing."""

    return {
        "task_id": task.get("task_id"),
        "title": task.get("title"),
        "task_type": task.get("task_type"),
        "status": task.get("status"),
        "intent_id": task.get("intent_id"),
        "decision_count": len(task.get("decision_ids", [])),
        "updated_at": task.get("updated_at"),
    }


async def load_os_collections(
    store: GoogleCloudStore,
) -> dict[str, list[dict[str, Any]]]:
    loaded = await asyncio.gather(
        *(store.list_documents(collection) for collection in OS_COLLECTIONS)
    )
    return {
        collection: [clean(item) for item in items]
        for collection, items in zip(OS_COLLECTIONS, loaded, strict=True)
    }


async def ensure_global_conversation(store: GoogleCloudStore) -> None:
    if await store.get("conversations", GLOBAL_CONVERSATION_ID) is not None:
        return
    conversation = Conversation(
        conversation_id=GLOBAL_CONVERSATION_ID,
        kind=ConversationKind.GLOBAL_PERSONAL_AGENT,
        participant_ids=["qi-owner", "qi-agent"],
    )
    await store.create(
        "conversations",
        GLOBAL_CONVERSATION_ID,
        conversation.model_dump(mode="json"),
    )


async def write_conversation_message(
    store: GoogleCloudStore,
    *,
    conversation_id: str,
    task_id: str | None,
    role: ConversationRole,
    author_id: str,
    content: str,
    directive_ids: list[str] | None = None,
) -> dict[str, Any]:
    message_id = f"conversation_message_{uuid4().hex}"
    message = ConversationMessage(
        message_id=message_id,
        conversation_id=conversation_id,
        task_id=task_id,
        role=role,
        author_id=author_id,
        content=content,
        presentation_directive_ids=directive_ids or [],
    )
    document = message.model_dump(mode="json")
    await store.create("conversation_messages", message_id, document)
    return document


async def create_presentation_directive(
    store: GoogleCloudStore,
    *,
    action: PresentationAction,
    explanation: str,
    task_id: str | None,
    entity_ids: list[str],
    presentation: PresentationMode = PresentationMode.INLINE_CARD,
) -> dict[str, Any]:
    directive_id = f"directive_{uuid4().hex}"
    directive = PresentationDirective(
        directive_id=directive_id,
        action=action,
        presentation=presentation,
        task_id=task_id,
        entity_ids=entity_ids,
        explanation=explanation,
    )
    document = directive.model_dump(mode="json")
    await store.create("presentation_directives", directive_id, document)
    await store.write_event(
        event_type="ui.directive.emitted",
        run_id=task_id or "global-personal-agent",
        producer="qi-agent",
        payload={"directiveId": directive_id, "action": action.value},
        idempotency_key=f"ui.directive.emitted:{directive_id}",
    )
    return document


async def create_task_workspace(
    store: GoogleCloudStore,
    *,
    intent_id: str,
    raw_goal: str,
    title: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    task_id = f"task_{uuid4().hex[:20]}"
    conversation_id = f"conversation_{task_id}"
    now = datetime.now(UTC)
    decision_id = f"decision_review_{task_id}"
    task = TaskWorkspace(
        task_id=task_id,
        title=title,
        task_type="conference_room_share",
        goal=raw_goal,
        status=TaskStatus.DRAFT,
        conversation_id=conversation_id,
        intent_id=intent_id,
        decision_ids=[decision_id],
        created_at=now,
        updated_at=now,
    )
    conversation = Conversation(
        conversation_id=conversation_id,
        kind=ConversationKind.TASK_USER_AGENT,
        task_id=task_id,
        participant_ids=["qi-owner", "qi-agent"],
        created_at=now,
        updated_at=now,
    )
    decision = DecisionInboxItem(
        decision_id=decision_id,
        task_id=task_id,
        type=DecisionType.REVIEW_POST_DRAFT,
        title="Review Qi's post draft",
        summary="Confirm what is public, agent-only and protected before publishing.",
        authoritative_entity_ids=[intent_id],
        expires_at=now + timedelta(days=7),
        created_at=now,
    )
    await asyncio.gather(
        store.create("task_workspaces", task_id, task.model_dump(mode="json")),
        store.create(
            "conversations", conversation_id, conversation.model_dump(mode="json")
        ),
        store.create("decision_inbox", decision_id, decision.model_dump(mode="json")),
    )
    intent = await store.get("intents", intent_id)
    if intent is not None:
        intent.pop("_updateTime", None)
        intent.update(
            task_id=task_id,
            authorship={
                "drafted_by_agent_id": "qi-agent",
                "approved_by_owner": False,
                "demo_data": False,
            },
        )
        await store.upsert("intents", intent_id, intent)
    await store.write_event(
        event_type="task.created",
        run_id=task_id,
        producer="qi-agent",
        payload={"taskId": task_id, "intentId": intent_id},
        idempotency_key=f"task.created:{task_id}",
    )
    return task.model_dump(mode="json"), decision.model_dump(mode="json")


async def find_task_by_intent(
    store: GoogleCloudStore, intent_id: str
) -> dict[str, Any] | None:
    return next(
        (
            clean(task)
            for task in await store.list_documents("task_workspaces")
            if task.get("intent_id") == intent_id
        ),
        None,
    )


async def update_task_after_publish(
    store: GoogleCloudStore, *, intent_id: str
) -> None:
    task = await find_task_by_intent(store, intent_id)
    if task is None:
        return
    now = datetime.now(UTC)
    task.update(status=TaskStatus.SEARCHING.value, updated_at=now)
    await store.upsert("task_workspaces", str(task["task_id"]), task)
    for decision_id in task.get("decision_ids", []):
        decision = await store.get("decision_inbox", str(decision_id))
        if decision and decision.get("type") == DecisionType.REVIEW_POST_DRAFT.value:
            decision.pop("_updateTime", None)
            decision.update(status=DecisionStatus.RESOLVED.value, resolved_at=now)
            await store.upsert("decision_inbox", str(decision_id), decision)
    intent = await store.get("intents", intent_id)
    if intent is not None:
        intent.pop("_updateTime", None)
        authorship = dict(intent.get("authorship", {}))
        authorship.update(
            drafted_by_agent_id="qi-agent",
            approved_by_owner=True,
            approved_at=now.isoformat(),
        )
        intent["task_id"] = str(task["task_id"])
        intent["authorship"] = authorship
        await store.upsert("intents", intent_id, intent)


def _room_id(pair_session_id: str) -> str:
    return f"room_{pair_session_id}"


async def materialize_task_run(
    store: GoogleCloudStore,
    *,
    task: dict[str, Any],
    state: dict[str, Any],
) -> None:
    """Project real run evidence into product rooms, assessments and decisions."""

    task_id = str(task["task_id"])
    source_intent_id = str(task["intent_id"])
    now = datetime.now(UTC)
    messages = list(state.get("messages", []))
    proposals = list(state.get("proposals", []))
    approvals = list(state.get("approvalRequests", []))
    matches = list(state.get("matches", []))
    beliefs = list(state.get("beliefs", []))
    peers = list(state.get("peerIntents", []))
    run = state.get("run") or {}
    run_id = str(run.get("runId", task_id))
    room_by_target: dict[str, str] = {}
    for peer in peers:
        target_intent_id = str(peer.get("intent_id", ""))
        agent_id = str(peer.get("owner_agent_id", ""))
        peer_messages = [
            message
            for message in messages
            if target_intent_id
            in {message.get("fromIntentId"), message.get("toIntentId")}
        ]
        if not peer_messages:
            continue
        pair_id = str(peer_messages[0].get("pairSessionId") or target_intent_id)
        room_id = _room_id(pair_id)
        room_by_target[target_intent_id] = room_id
        matched = any(item.get("candidateAgentId") == agent_id for item in matches)
        target_approval = next(
            (
                item
                for item in approvals
                if item.get("targetIntentId") == target_intent_id
            ),
            None,
        )
        room = CoordinationRoom(
            room_id=room_id,
            task_id=task_id,
            source_intent_id=source_intent_id,
            target_intent_id=target_intent_id,
            participant_agent_ids=["qi-agent", agent_id],
            room_type=(
                RoomType.SHARED_COORDINATION_ROOM
                if matched
                else RoomType.NEGOTIATION_ROOM
            ),
            status=(
                RoomStatus.COMPLETED
                if matched
                else RoomStatus.NEEDS_INPUT
                if target_approval
                else RoomStatus.ACTIVE
            ),
            autonomy_mode=(AutonomyMode.HUMAN if matched else AutonomyMode.AGENT),
            human_participation_available=matched,
            latest_meaningful_event=(
                "Match committed; synthetic shared room unlocked"
                if matched
                else "Proposal accepted; your decision is required"
                if target_approval
                else "Agents exchanged task-scoped evidence"
            ),
            updated_at=now,
        )
        await store.upsert("coordination_rooms", room_id, room.model_dump(mode="json"))
        for message in peer_messages:
            message_id = str(message.get("messageId"))
            if not message_id:
                continue
            room_message = RoomMessage(
                message_id=f"room_message_{message_id}",
                room_id=room_id,
                task_id=task_id,
                source_intent_id=source_intent_id,
                target_intent_id=target_intent_id,
                speaker_id=str(message.get("fromAgentId")),
                speaker_type=SpeakerType.PERSONAL_AGENT,
                authorship=MessageAuthorship.AGENT_SENT_WITHIN_AUTHORITY,
                visibility=MessageVisibility.AGENTS_ONLY,
                content=str(message.get("naturalLanguage")),
                provenance={"run_id": run_id, "a2a_message_id": message_id},
                created_at=now,
            )
            await store.upsert(
                "room_messages",
                room_message.message_id,
                room_message.model_dump(mode="json"),
            )
        disposition = next(
            (
                belief
                for belief in beliefs
                if belief.get("subjectAgentId") == agent_id
                and belief.get("field") == "qi_disposition"
            ),
            None,
        )
        candidate_proposal = next(
            (item for item in proposals if item.get("candidateAgentId") == agent_id),
            None,
        )
        if matched or target_approval:
            band = CandidatePriorityBand.RECOMMENDED
            explanation = (
                "Current accepted proposal is backed by the stored negotiation."
            )
        elif disposition and disposition.get("value") == "WITHDRAW":
            band = CandidatePriorityBand.CLOSED
            explanation = str(
                disposition.get("observableReason")
                or "Qi ended this conversation from recorded evidence."
            )
        elif candidate_proposal:
            band = CandidatePriorityBand.PROMISING
            explanation = "A stored proposal exists and remains under evaluation."
        else:
            band = CandidatePriorityBand.NEEDS_INFORMATION
            explanation = "The agents exchanged evidence; no accepted proposal exists."
        constraints = dict(peer.get("public_constraints", {}))
        assessment = CandidateAssessment(
            assessment_id=f"assessment_{task_id}_{target_intent_id}",
            task_id=task_id,
            candidate_intent_id=target_intent_id,
            candidate_agent_id=agent_id,
            priority_band=band,
            current_status=room.status.value,
            verified_support=[
                f"Published event: {constraints.get('event', '—')}",
                f"Published location: {constraints.get('location', '—')}",
                (
                    "Published dates: "
                    f"{constraints.get('date_start', '—')} to "
                    f"{constraints.get('date_end', '—')}"
                ),
            ],
            peer_reported_support=[
                "Peer Agent supplied task-scoped compatibility evidence"
            ],
            negotiated_support=(
                ["A current versioned proposal exists"] if candidate_proposal else []
            ),
            conflicts=(
                [str(disposition.get("observableReason"))]
                if disposition and disposition.get("value") == "WITHDRAW"
                else []
            ),
            uncertainties=["Peer-reported routine is not independently verified"],
            relationship_path=(
                ["qi-agent", "alice-agent", agent_id]
                if any(
                    message.get("fromAgentId") == "alice-agent"
                    for message in messages
                )
                and agent_id in {"maya-agent", "lena-agent"}
                else ["qi-agent", agent_id]
            ),
            active_room_id=room_id,
            active_proposal_id=(
                str(candidate_proposal.get("proposalId"))
                if candidate_proposal
                else None
            ),
            evidence_event_ids=[
                run_id,
                *[str(item.get("messageId")) for item in peer_messages],
            ],
            last_updated_turn_id=(
                str(state.get("turns", [])[-1].get("turnId"))
                if state.get("turns")
                else None
            ),
            observable_explanation=explanation,
            updated_at=now,
        )
        await store.upsert(
            "candidate_assessments",
            assessment.assessment_id,
            assessment.model_dump(mode="json"),
        )
    if matches:
        task.update(
            status=TaskStatus.COMPLETED.value,
            match_id=str(matches[-1].get("matchId") or matches[-1].get("match_id")),
        )
        for decision_id in task.get("decision_ids", []):
            stored_decision = await store.get("decision_inbox", str(decision_id))
            if (
                stored_decision
                and stored_decision.get("status") == DecisionStatus.OPEN.value
            ):
                stored_decision.pop("_updateTime", None)
                stored_decision.update(
                    status=DecisionStatus.RESOLVED.value,
                    resolved_at=now,
                )
                await store.upsert(
                    "decision_inbox", str(decision_id), stored_decision
                )
        memories = [
            item
            for item in await store.list_documents("memories")
            if item.get("runId") == run_id
        ]
        for memory in memories:
            memory_id = str(
                memory.get("memoryId")
                or memory.get("memory_id")
                or memory.get("_id")
            )
            decision_id = f"decision_memory_{memory_id}"
            memory_decision = DecisionInboxItem(
                decision_id=decision_id,
                task_id=task_id,
                type=DecisionType.CONFIRM_MEMORY,
                title="Review what Qi learned",
                summary="Confirm, correct, archive or restrict this scoped inference.",
                authoritative_entity_ids=[memory_id],
            )
            await store.upsert(
                "decision_inbox",
                decision_id,
                memory_decision.model_dump(mode="json"),
            )
            decision_ids = list(task.get("decision_ids", []))
            if decision_id not in decision_ids:
                decision_ids.append(decision_id)
            task["decision_ids"] = decision_ids
    elif approvals:
        task.update(
            status=TaskStatus.NEEDS_DECISION.value,
            active_proposal_id=str(approvals[-1].get("proposalId")),
        )
        decision_id = f"decision_approval_{approvals[-1].get('proposalId')}"
        approval_decision = DecisionInboxItem(
            decision_id=decision_id,
            task_id=task_id,
            type=DecisionType.APPROVE_PROPOSAL,
            title="Maya's Agent accepted a proposal",
            summary="Review the current exact-effect contract before commitment.",
            authoritative_entity_ids=[str(approvals[-1].get("proposalId"))],
            expires_at=(
                datetime.fromisoformat(
                    str(approvals[-1].get("holdExpiresAt")).replace("Z", "+00:00")
                )
                if approvals[-1].get("holdExpiresAt")
                else None
            ),
        )
        await store.upsert(
            "decision_inbox",
            decision_id,
            approval_decision.model_dump(mode="json"),
        )
        decision_ids = list(task.get("decision_ids", []))
        if decision_id not in decision_ids:
            decision_ids.append(decision_id)
        task["decision_ids"] = decision_ids
    elif messages:
        task["status"] = TaskStatus.ACTIVE_NEGOTIATION.value
    task["updated_at"] = now
    await store.upsert("task_workspaces", task_id, task)


async def build_os_bootstrap(
    store: GoogleCloudStore, *, demo_state: dict[str, Any]
) -> dict[str, Any]:
    await ensure_global_conversation(store)
    data = await load_os_collections(store)
    tasks = sorted(
        data["task_workspaces"],
        key=lambda task: (
            TASK_PRIORITY.get(str(task.get("status")), 99),
            str(task.get("updated_at", "")),
        ),
    )
    post_candidates = list(demo_state.get("intentRegistry", []))
    active_intent = demo_state.get("activeIntent")
    if active_intent and not any(
        item.get("intent_id") == active_intent.get("intent_id")
        for item in post_candidates
    ):
        post_candidates.append(active_intent)
    latest_posts = [
        post
        for post in post_candidates
        if post.get("owner_agent_id") == "qi-agent"
        or post.get("status") == "OPEN"
    ]
    return {
        "personalAgent": {
            "agentId": "qi-agent",
            "displayName": "Qi Agent",
            "ownerDisplayName": "Qi",
            "persistentIdentity": True,
        },
        "tasks": tasks,
        "taskSummaries": [public_task_summary(task) for task in tasks],
        "conversations": data["conversations"],
        "conversationMessages": sorted(
            data["conversation_messages"],
            key=lambda item: str(item.get("created_at", "")),
        ),
        "decisions": sorted(
            data["decision_inbox"],
            key=lambda item: (
                item.get("status") != DecisionStatus.OPEN.value,
                str(item.get("created_at", "")),
            ),
        ),
        "candidateAssessments": data["candidate_assessments"],
        "rooms": data["coordination_rooms"],
        "roomMessages": sorted(
            data["room_messages"],
            key=lambda item: str(item.get("created_at", "")),
        ),
        "presentationDirectives": data["presentation_directives"],
        "internalWorkerRuns": data["internal_worker_runs"],
        "explorePosts": latest_posts,
        "demoState": demo_state,
        "implementationTruth": {
            "dynamicWorkersImplemented": False,
            "peerHumansAreSynthetic": True,
            "sharedRoomIsSyntheticDemo": True,
        },
    }
