from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.multi_user_platform import stable_id
from pairpilot_orchestrator.v2_connections import (
    get_connection_detail,
    list_connections_for_user,
    record_connection_usage,
    set_connection_preference,
)
from test_multi_user_platform import MemoryMultiUserStore


def principal(uid: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        uid=uid, email=f"{uid}@private.example", email_verified=True
    )


async def seed_connection(store: MemoryMultiUserStore) -> str:
    owner_agent = stable_id("agent", "owner")
    peer_agent = stable_id("agent", "peer")
    for uid, agent_id in (("owner", owner_agent), ("peer", peer_agent)):
        await store.create(
            "users",
            uid,
            {
                "namespace": "production",
                "uid": uid,
                "display_name": uid.title(),
                "email": f"{uid}@login.private",
                "personal_agent_id": agent_id,
            },
        )
        await store.create(
            "personal_agents",
            agent_id,
            {
                "namespace": "production",
                "agent_id": agent_id,
                "owner_uid": uid,
                "display_name": f"{uid.title()} Agent",
            },
        )
    await store.create(
        "communities",
        "community_conf",
        {
            "namespace": "production",
            "community_id": "community_conf",
            "name": "AI Conference",
            "location": "Seoul",
        },
    )
    connection_id = stable_id("relationship", "owner", peer_agent)
    await store.create(
        "relationships",
        connection_id,
        {
            "namespace": "production",
            "relationship_id": connection_id,
            "owner_uid": "owner",
            "owner_agent_id": owner_agent,
            "peer_agent_id": peer_agent,
            "peer_owner_uid_internal": "peer",
            "relation_type": "SUCCESSFUL_COORDINATION",
            "introduction_path": "DIRECT_COMMUNITY_POST",
            "relevant_communities": ["community_conf"],
            "task_type_compatibility": ["EVENT_BUDDY"],
            "plans_committed": 2,
            "plans_reported": 1,
            "successful_plans": 1,
            "cancellation_history": 1,
            "commitment_inaccuracy_reports": 0,
            "would_coordinate_again_yes": 1,
            "last_interaction_at": datetime.now(UTC),
        },
    )
    await store.create(
        "matches",
        "match_shared",
        {
            "namespace": "production",
            "match_id": "match_shared",
            "participant_uids": ["owner", "peer"],
            "participant_agent_ids": [owner_agent, peer_agent],
            "status": "COMPLETED",
            "terms": {"title": "Conference buddy plan", "task_type": "EVENT_BUDDY"},
        },
    )
    await store.create(
        "coordination_rooms",
        "room_shared",
        {
            "namespace": "production",
            "room_id": "room_shared",
            "participant_uids": ["owner", "peer"],
            "state": "SHARED",
            "room_type": "SHARED_COORDINATION_ROOM",
        },
    )
    await store.create(
        "relationship_events",
        "event_shared",
        {
            "namespace": "production",
            "relationship_event_id": "event_shared",
            "relationship_id": connection_id,
            "owner_uid": "owner",
            "match_id": "match_shared",
            "event_type": "AUTHORITATIVE_OWNER_OUTCOME",
            "source": "MATCH_PARTICIPANT_CHECK_IN",
            "did_plan_happen": True,
            "created_at": datetime.now(UTC),
        },
    )
    return connection_id


@pytest.mark.asyncio
async def test_connection_list_is_owner_scoped_safe_and_grouped() -> None:
    store = MemoryMultiUserStore()
    connection_id = await seed_connection(store)
    payload = await list_connections_for_user(store, principal("owner"))

    assert payload["count"] == 1
    assert payload["connections"][0]["connection_id"] == connection_id
    assert payload["connections"][0]["person"]["display_name"] == "Peer"
    assert payload["connections"][0]["state"] == "ESTABLISHED"
    assert len(payload["views"]["TRUSTED"]) == 1
    assert len(payload["views"]["NEEDS_REVIEW"]) == 1
    assert "login.private" not in str(payload)
    assert "peer_owner_uid_internal" not in str(payload)


@pytest.mark.asyncio
async def test_connection_detail_explains_context_and_provenance() -> None:
    store = MemoryMultiUserStore()
    connection_id = await seed_connection(store)
    detail = await get_connection_detail(store, principal("owner"), connection_id)

    assert detail["shared_communities"][0]["name"] == "AI Conference"
    assert detail["plans"][0]["state"] == "COMPLETED"
    assert detail["active_rooms"][0]["room_id"] == "room_shared"
    assert detail["provenance_events"][0]["event_type"] == "AUTHORITATIVE_OWNER_OUTCOME"
    dimensions = {item["dimension"]: item for item in detail["relationship_dimensions"]}
    assert dimensions["privacy_respect"]["value"] == "NOT_ENOUGH_EVIDENCE"
    assert detail["shared_connections"] == []
    with pytest.raises((LookupError, HTTPException)):
        await get_connection_detail(store, principal("peer"), connection_id)


@pytest.mark.asyncio
async def test_connection_preferences_do_not_mutate_relationship_evidence() -> None:
    store = MemoryMultiUserStore()
    connection_id = await seed_connection(store)
    before = await store.get("relationships", connection_id)
    muted = await set_connection_preference(
        store, principal("owner"), connection_id=connection_id, muted=True
    )
    assert muted["muted"] is True
    listing = await list_connections_for_user(store, principal("owner"))
    assert listing["connections"][0]["state"] == "MUTED"
    assert await store.get("relationships", connection_id) == before


@pytest.mark.asyncio
async def test_connection_usage_is_task_contextual_and_provenance_backed() -> None:
    store = MemoryMultiUserStore()
    connection_id = await seed_connection(store)
    await store.create(
        "task_workspaces",
        "task_event",
        {
            "namespace": "production",
            "task_id": "task_event",
            "owner_uid": "owner",
            "task_type": "EVENT_BUDDY",
        },
    )
    await store.create(
        "task_workspaces",
        "task_room",
        {
            "namespace": "production",
            "task_id": "task_room",
            "owner_uid": "owner",
            "task_type": "ROOM_SHARE",
        },
    )

    applicable = await record_connection_usage(
        store,
        principal("owner"),
        connection_id=connection_id,
        task_id="task_event",
        purpose="PRIORITIZE_FOR_TASK",
    )
    mismatch = await record_connection_usage(
        store,
        principal("owner"),
        connection_id=connection_id,
        task_id="task_room",
        purpose="REQUEST_WARM_INTRODUCTION",
    )
    assert applicable["context_applicable"] is True
    assert mismatch["context_applicable"] is False
    assert len(store.collections["relationship_usage_events"]) == 2
    assert "content" not in str(applicable)
