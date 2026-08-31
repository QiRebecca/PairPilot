"""Run conversational tests A-G with live Gemini and an isolated memory store."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime
from typing import Any

from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.multi_user_platform import (
    create_user_task,
    provision_user,
)
from pairpilot_orchestrator.personal_agent_chat import stream_personal_agent_turn
from pairpilot_schemas import CreateUserTaskInput
from test_multi_user_platform import MemoryMultiUserStore


async def _turn(
    store: MemoryMultiUserStore,
    principal: AuthenticatedPrincipal,
    conversation: dict[str, Any],
    content: str,
    sequence: int,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    async for event in stream_personal_agent_turn(
        store,
        principal,
        conversation=conversation,
        content=content,
        client_message_id=f"acceptance-message-{principal.uid}-{sequence}",
        invocation_id=f"acceptance-invocation-{principal.uid}-{sequence}",
    ):
        events.append(event)
    completed = next(
        (event for event in events if event["type"] == "agent.completed"), None
    )
    if completed is None:
        raise RuntimeError(f"live turn {sequence} failed")
    return {
        "events": events,
        "message": completed["message"],
        "tools": [
            event.get("tool_name")
            for event in events
            if event["type"] == "tool.started"
        ],
    }


def _principal(uid: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        uid=uid,
        email=f"{uid}@acceptance.invalid",
        email_verified=True,
    )


async def main() -> None:
    store = MemoryMultiUserStore()
    user_a = _principal("acceptance-user-a")
    user_b = _principal("acceptance-user-b")
    await provision_user(store, user_a, now=datetime.now(UTC))
    await provision_user(store, user_b, now=datetime.now(UTC))
    global_a = store.collections["conversations"]["user:acceptance-user-a:global"]
    global_b = store.collections["conversations"]["user:acceptance-user-b:global"]

    test_a = await _turn(
        store,
        user_a,
        global_a,
        (
            "I’m attending a conference in Seoul and would like to share a room "
            "with another woman. I am flexible on dates but care a lot about quiet "
            "nights."
        ),
        1,
    )
    test_b = await _turn(
        store,
        user_a,
        global_a,
        "What did I just say mattered most?",
        2,
    )
    if "quiet" not in str(test_b["message"]["content"]).casefold():
        raise RuntimeError("Test B did not recall quiet nights")
    if test_a["message"]["adk_session_id"] != test_b["message"]["adk_session_id"]:
        raise RuntimeError("Test B did not resume the same ADK session")

    task = await create_user_task(
        store,
        user_a,
        CreateUserTaskInput(
            title="Acceptance conference room share",
            task_type="conference_room_share",
            goal="Find a quiet conference roommate in Seoul.",
            event="AcceptanceConf",
            location="Seoul",
            date_start=date(2026, 10, 10),
            date_end=date(2026, 10, 13),
            public_requirements=["adult attendee", "non-smoking"],
            maximum_additional_cost_usd=70,
            partial_date_overlap_allowed=True,
        ),
    )
    task_id = str(task["task_id"])
    intent_id = str(task["intent_id"])
    private = store.collections["intent_private_data"][intent_id]
    private["public_draft"] = {
        "public_title": "AcceptanceConf quiet room share",
        "public_summary": "Looking for an adult attendee to share a room in Seoul.",
        "public_requirements": ["adult attendee", "non-smoking"],
    }
    await store.upsert("intent_private_data", intent_id, private)
    task_conversation = store.collections["conversations"][str(task["conversation_id"])]

    test_c = await _turn(
        store,
        user_a,
        task_conversation,
        "Actually, my additional budget limit is only $45. Update this request.",
        3,
    )
    if "revise_intent_post" not in test_c["tools"]:
        raise RuntimeError("Test C did not select revise_intent_post")
    updated_private = store.collections["intent_private_data"][intent_id]
    budget = dict(updated_private["agent_only_constraints"])[
        "maximum_additional_cost_usd"
    ]
    if budget != 45:
        raise RuntimeError("Test C did not persist the $45 boundary")

    test_d = await _turn(
        store,
        user_a,
        task_conversation,
        "What are you currently doing for this request? Read the current state.",
        4,
    )
    if "inspect_task_status" not in test_d["tools"]:
        raise RuntimeError("Test D did not inspect authoritative task status")

    assessment_id = "acceptance-assessment-maya"
    await store.create(
        "candidate_assessments",
        assessment_id,
        {
            "namespace": "production",
            "assessment_id": assessment_id,
            "owner_uid": user_a.uid,
            "task_id": task_id,
            "candidate_agent_id": "maya-agent",
            "candidate_intent_id": "acceptance-peer-intent",
            "summary": (
                "Maya’s public dates overlap and her Agent reports quiet nights."
            ),
            "disposition": "PREFERRED",
        },
    )
    test_e = await _turn(
        store,
        user_a,
        task_conversation,
        "Show me why you prefer Maya. Use an authoritative comparison card.",
        5,
    )
    directives = [
        event for event in test_e["events"] if event["type"] == "ui.directive"
    ]
    if not directives:
        raise RuntimeError("Test E did not emit a UI directive")

    await store.create(
        "intent_posts",
        "acceptance-peer-intent",
        {
            "namespace": "production",
            "intent_id": "acceptance-peer-intent",
            "owner_uid": user_b.uid,
            "owner_agent_id": "acceptance-peer-agent",
            "public_title": "AcceptanceConf room share",
            "public_summary": "Adult attendee looking to coordinate a shared room.",
            "public_requirements": ["adult attendee", "non-smoking"],
            "public_constraints": {
                "event": "AcceptanceConf",
                "location": "Seoul",
                "date_start": "2026-10-10",
                "date_end": "2026-10-13",
            },
            "status": "OPEN",
        },
    )
    test_f = await _turn(
        store,
        user_a,
        task_conversation,
        (
            "Ask the other Agent for acceptance-peer-intent whether there will be "
            "late-night calls, but don’t tell them why I care. Store my private "
            "instruction and send only the minimum necessary question."
        ),
        6,
    )
    required_f_tools = {
        "send_private_task_instruction",
        "send_intent_scoped_a2a_message",
    }
    if not required_f_tools.issubset(set(test_f["tools"])):
        raise RuntimeError(f"Test F tools were {test_f['tools']}")
    outbound = next(iter(store.collections["a2a_requests"].values()))
    outbound_text = str(outbound["minimum_necessary_message"]).casefold()
    if "quiet" in outbound_text or "why" in outbound_text:
        raise RuntimeError("Test F leaked the private reason")

    test_g = await _turn(
        store,
        user_b,
        global_b,
        "I want to organize a morning chess group in Tokyo. What do you need to know?",
        1,
    )
    if test_g["message"]["adk_session_id"] == test_b["message"]["adk_session_id"]:
        raise RuntimeError("Test G reused User A's ADK session")
    response_g = str(test_g["message"]["content"]).casefold()
    if "quiet nights" in response_g or "seoul" in response_g:
        raise RuntimeError("Test G leaked User A context")

    print(
        json.dumps(
            {
                "status": "PASS",
                "tests": {
                    "A": {
                        "invocation": test_a["message"]["adk_invocation_id"],
                        "toolsOrClarification": test_a["tools"] or ["clarification"],
                    },
                    "B": {
                        "sameAdkSession": True,
                        "session": test_b["message"]["adk_session_id"],
                    },
                    "C": {"tools": test_c["tools"], "budget": budget},
                    "D": {"tools": test_d["tools"]},
                    "E": {"tools": test_e["tools"], "directiveCount": len(directives)},
                    "F": {"tools": test_f["tools"], "privateReasonLeaked": False},
                    "G": {
                        "separateAdkSession": True,
                        "userAContextLeaked": False,
                    },
                },
                "model": "gemini-3.7-flash",
                "executionMode": "LIVE GEMINI + GOOGLE ADK + A2A",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
