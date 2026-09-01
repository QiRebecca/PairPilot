from __future__ import annotations

import pytest
from fastapi import HTTPException
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.multi_user_platform import send_user_room_message
from pairpilot_orchestrator.v2_rooms import (
    get_room_workspace,
    list_rooms_for_user,
    send_room_channel_message,
    set_room_muted,
)
from test_multi_user_platform import MemoryMultiUserStore


def principal(uid: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        uid=uid,
        email=f"{uid}@example.com",
        email_verified=True,
    )


async def seed_user(store: MemoryMultiUserStore, uid: str) -> None:
    await store.create(
        "users",
        uid,
        {
            "namespace": "production",
            "uid": uid,
            "display_name": uid.title(),
            "personal_agent_id": f"agent_{uid}",
            "email": f"{uid}@private.example",
        },
    )


async def seed_room(
    store: MemoryMultiUserStore,
    *,
    unlocked: bool = False,
    status: str = "NEEDS_INPUT",
) -> None:
    await seed_user(store, "viewer")
    await seed_user(store, "peer")
    await store.create(
        "coordination_rooms",
        "room_pair",
        {
            "schema_version": 4,
            "namespace": "production",
            "room_id": "room_pair",
            "participant_uids": ["viewer", "peer"],
            "participant_agent_ids": ["agent_viewer", "agent_peer"],
            "room_type": (
                "SHARED_COORDINATION_ROOM" if unlocked else "NEGOTIATION_ROOM"
            ),
            "status": status,
            "human_participation_available": unlocked,
            "visibility": "SHARED_ROOM" if unlocked else "AGENTS_ONLY",
        },
    )
    await store.create(
        "user_autonomy_configs",
        "viewer",
        {"owner_uid": "viewer", "default_mode": "COPILOT"},
    )


@pytest.mark.asyncio
async def test_room_workspace_separates_all_channels_and_redacts_agent_transcript() -> (
    None
):
    store = MemoryMultiUserStore()
    await seed_room(store, unlocked=True)
    messages = [
        (
            "private-viewer",
            {
                "owner_uid": "viewer",
                "visibility": "PRIVATE_USER_AGENT",
                "content": "My private instruction",
            },
        ),
        (
            "private-peer",
            {
                "owner_uid": "peer",
                "visibility": "PRIVATE_USER_AGENT",
                "content": "Peer secret instruction",
            },
        ),
        (
            "agents",
            {
                "visibility": "AGENTS_ONLY",
                "content": "Email peer@secret.example and meet at hotel room 1204",
            },
        ),
        (
            "shared",
            {
                "visibility": "SHARED_ROOM",
                "content": "See you in the lobby.",
            },
        ),
    ]
    for message_id, fields in messages:
        await store.create(
            "room_messages",
            message_id,
            {
                "namespace": "production",
                "message_id": message_id,
                "room_id": "room_pair",
                "speaker_id": "speaker",
                "speaker_type": "PERSONAL_AGENT",
                "authorship": "AGENT_SENT_WITHIN_AUTHORITY",
                **fields,
            },
        )

    payload = await get_room_workspace(store, principal("viewer"), "room_pair")

    assert [
        item["message_id"] for item in payload["channels"]["PRIVATE_USER_AGENT"]
    ] == ["private-viewer"]
    agent_message = payload["channels"]["AGENTS_ONLY"][0]
    assert "peer@secret.example" not in agent_message["content"]
    assert "1204" not in agent_message["content"]
    assert agent_message["policy_redacted"] is True
    assert payload["channels"]["SHARED_ROOM"][0]["message_id"] == "shared"
    assert payload["channel_permissions"]["AGENTS_ONLY"]["write"] is False
    assert "@private.example" not in str(payload)


@pytest.mark.asyncio
async def test_private_instruction_never_enters_shared_or_agents_only_channel() -> None:
    store = MemoryMultiUserStore()
    await seed_room(store)
    await send_room_channel_message(
        store,
        principal("viewer"),
        room_id="room_pair",
        channel="PRIVATE_USER_AGENT",
        content="Privately ask whether timing is flexible.",
        authorship="HUMAN_WRITTEN",
        idempotency_key="private-message-1",
        reply_to=None,
    )
    payload = await get_room_workspace(store, principal("viewer"), "room_pair")
    assert len(payload["channels"]["PRIVATE_USER_AGENT"]) == 1
    assert payload["channels"]["AGENTS_ONLY"] == []
    assert payload["channels"]["SHARED_ROOM"] == []


@pytest.mark.asyncio
async def test_human_cannot_write_agents_only_or_locked_shared_channel() -> None:
    store = MemoryMultiUserStore()
    await seed_room(store)
    common = {
        "store": store,
        "principal": principal("viewer"),
        "room_id": "room_pair",
        "content": "Hello",
        "authorship": "HUMAN_WRITTEN",
        "idempotency_key": "message-key-1",
        "reply_to": None,
    }
    with pytest.raises(PermissionError, match="HUMAN_CANNOT_WRITE_AGENTS_ONLY"):
        await send_room_channel_message(channel="AGENTS_ONLY", **common)
    with pytest.raises(PermissionError, match="SHARED_ROOM_NOT_UNLOCKED"):
        await send_room_channel_message(channel="SHARED_ROOM", **common)


@pytest.mark.asyncio
async def test_unlocked_shared_channel_enforces_privacy() -> None:
    store = MemoryMultiUserStore()
    await seed_room(store, unlocked=True)
    common = {
        "store": store,
        "principal": principal("viewer"),
        "room_id": "room_pair",
        "channel": "SHARED_ROOM",
        "authorship": "HUMAN_WRITTEN",
        "reply_to": None,
    }
    with pytest.raises(ValueError, match="identifying detail"):
        await send_room_channel_message(
            content="Email me at private@example.com",
            idempotency_key="shared-message-contact",
            **common,
        )
    message = await send_room_channel_message(
        content="I can meet in the public lobby at 8:30.",
        idempotency_key="shared-message-safe",
        **common,
    )
    assert message["visibility"] == "SHARED_ROOM"
    assert message["speaker_type"] == "HUMAN"

    with pytest.raises(ValueError, match="identifying detail"):
        await send_user_room_message(
            store,
            principal("viewer"),
            room_id="room_pair",
            content="My phone is +1 415 555 0199",
            authorship="HUMAN_WRITTEN",
            idempotency_key="legacy-shared-message-contact",
        )


@pytest.mark.asyncio
async def test_nonparticipant_cannot_read_write_or_mute_room() -> None:
    store = MemoryMultiUserStore()
    await seed_room(store)
    outsider = principal("outsider")
    with pytest.raises(HTTPException) as read_denied:
        await get_room_workspace(store, outsider, "room_pair")
    assert read_denied.value.status_code == 403
    with pytest.raises(HTTPException):
        await send_room_channel_message(
            store,
            outsider,
            room_id="room_pair",
            channel="PRIVATE_USER_AGENT",
            content="unauthorized",
            authorship="HUMAN_WRITTEN",
            idempotency_key="outsider-message",
            reply_to=None,
        )
    with pytest.raises(HTTPException):
        await set_room_muted(store, outsider, room_id="room_pair", muted=True)


@pytest.mark.asyncio
async def test_room_list_uses_v2_sections_and_hides_internal_participants() -> None:
    store = MemoryMultiUserStore()
    await seed_room(store, status="WAITING_FOR_PEER")
    listing = await list_rooms_for_user(store, principal("viewer"))
    assert listing["count"] == 1
    assert listing["sections"]["WAITING_FOR_PEER"][0]["room_id"] == "room_pair"
    assert "participant_uids" not in listing["rooms"][0]
