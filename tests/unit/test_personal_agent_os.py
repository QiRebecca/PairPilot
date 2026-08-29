from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pairpilot_orchestrator import web
from pairpilot_orchestrator.personal_agent_os import (
    build_os_bootstrap,
    create_task_workspace,
    public_task_summary,
)
from pairpilot_schemas import (
    MessageAuthorship,
    MessageVisibility,
    PresentationAction,
    PresentationDirective,
    PresentationMode,
    RoomMessage,
    SpeakerType,
)
from pydantic import ValidationError


class MemoryStore:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, dict[str, Any]]] = {}
        self.events: list[dict[str, Any]] = []

    async def get(self, collection: str, document_id: str) -> dict[str, Any] | None:
        item = self.collections.get(collection, {}).get(document_id)
        return dict(item) if item else None

    async def list_documents(self, collection: str) -> list[dict[str, Any]]:
        return [
            {**item, "_id": document_id}
            for document_id, item in self.collections.get(collection, {}).items()
        ]

    async def create(
        self, collection: str, document_id: str, data: dict[str, Any]
    ) -> bool:
        target = self.collections.setdefault(collection, {})
        if document_id in target:
            return False
        target[document_id] = dict(data)
        return True

    async def upsert(
        self, collection: str, document_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        self.collections.setdefault(collection, {})[document_id] = dict(data)
        return data

    async def write_event(self, **event: Any) -> dict[str, Any]:
        self.events.append(event)
        return {"event_id": event["idempotency_key"], "created": True}


def test_presentation_directive_rejects_urls_and_unapproved_navigation() -> None:
    with pytest.raises(ValidationError, match="cannot contain URLs"):
        PresentationDirective(
            directive_id="directive_1",
            action=PresentationAction.SHOW_POST,
            entity_ids=["https://attacker.example"],
            explanation="Open the record",
        )
    with pytest.raises(ValidationError, match="cannot navigate"):
        PresentationDirective(
            directive_id="directive_2",
            action=PresentationAction.SHOW_MEMORY,
            presentation=PresentationMode.NAVIGATE,
            entity_ids=["memory_1"],
            explanation="Open memory",
        )


def test_human_cannot_write_directly_to_agents_only_transcript() -> None:
    with pytest.raises(ValidationError, match="humans cannot write directly"):
        RoomMessage(
            message_id="message_1",
            room_id="room_1",
            task_id="task_1",
            source_intent_id="intent_qi",
            target_intent_id="intent_maya",
            speaker_id="qi-owner",
            speaker_type=SpeakerType.HUMAN,
            authorship=MessageAuthorship.HUMAN_WRITTEN,
            visibility=MessageVisibility.AGENTS_ONLY,
            content="Post this directly",
            provenance={"source": "test"},
        )


@pytest.mark.asyncio
async def test_each_task_gets_an_isolated_conversation_and_decision() -> None:
    store = MemoryStore()
    first, first_decision = await create_task_workspace(
        store,  # type: ignore[arg-type]
        intent_id="intent_first",
        raw_goal="Find a quiet ICML roommate",
        title="ICML roommate",
    )
    second, second_decision = await create_task_workspace(
        store,  # type: ignore[arg-type]
        intent_id="intent_second",
        raw_goal="Find a small dinner group",
        title="Seoul dinner",
    )
    assert first["task_id"] != second["task_id"]
    assert first["conversation_id"] != second["conversation_id"]
    assert first_decision["task_id"] == first["task_id"]
    assert second_decision["task_id"] == second["task_id"]
    assert len(store.collections["conversations"]) == 2


def test_global_router_summary_is_bounded_and_excludes_task_goal() -> None:
    summary = public_task_summary(
        {
            "task_id": "task_1",
            "title": "ICML roommate",
            "task_type": "conference_room_share",
            "status": "SEARCHING",
            "intent_id": "intent_1",
            "goal": "protected long-form goal",
            "decision_ids": ["decision_1"],
            "updated_at": datetime.now(UTC),
        }
    )
    assert summary["decision_count"] == 1
    assert "goal" not in summary


@pytest.mark.asyncio
async def test_bootstrap_prioritizes_decisions_and_filters_explore_to_open() -> None:
    store = MemoryStore()
    store.collections["task_workspaces"] = {
        "task_search": {
            "task_id": "task_search",
            "title": "Search",
            "task_type": "room_share",
            "goal": "Search",
            "status": "SEARCHING",
            "conversation_id": "conversation_search",
            "intent_id": "intent_search",
        },
        "task_decision": {
            "task_id": "task_decision",
            "title": "Decision",
            "task_type": "room_share",
            "goal": "Decision",
            "status": "NEEDS_DECISION",
            "conversation_id": "conversation_decision",
            "intent_id": "intent_decision",
        },
    }
    demo_state = {
        "intentRegistry": [
            {"intent_id": "open", "status": "OPEN"},
            {"intent_id": "closed", "status": "MATCHED"},
        ],
        "activeIntent": {
            "intent_id": "mine",
            "owner_agent_id": "qi-agent",
            "status": "AWAITING_APPROVAL",
        },
    }
    result = await build_os_bootstrap(
        store,  # type: ignore[arg-type]
        demo_state=demo_state,
    )
    assert [task["task_id"] for task in result["tasks"]] == [
        "task_decision",
        "task_search",
    ]
    assert [post["intent_id"] for post in result["explorePosts"]] == [
        "open",
        "mine",
    ]
    assert result["personalAgent"]["agentId"] == "qi-agent"


def test_room_actions_keep_private_instructions_out_of_agents_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = MemoryStore()
    store.collections["coordination_rooms"] = {
        "room_1": {
            "room_id": "room_1",
            "task_id": "task_1",
            "source_intent_id": "intent_qi",
            "target_intent_id": "intent_maya",
            "room_type": "NEGOTIATION_ROOM",
            "human_participation_available": False,
        }
    }
    store.collections["task_workspaces"] = {
        "task_1": {
            "task_id": "task_1",
            "conversation_id": "conversation_task_1",
        }
    }
    monkeypatch.setattr(web, "_store", lambda: store)
    client = TestClient(web.app)
    private = client.post(
        "/api/os/rooms/room_1/messages",
        json={"action": "ASK_QI_TO_SEND", "content": "Ask about check-in time."},
    )
    assert private.status_code == 200
    assert private.json()["channel"] == "PRIVATE_USER_AGENT"
    assert private.json()["message"]["speaker_id"] == "qi-owner"
    assert private.json()["message"]["authorship"] == "HUMAN_WRITTEN"
    assert private.json()["message"]["visibility"] != "AGENTS_ONLY"

    shared = client.post(
        "/api/os/rooms/room_1/messages",
        json={"action": "SEND_AS_MYSELF", "content": "Hello Maya."},
    )
    assert shared.status_code == 409
