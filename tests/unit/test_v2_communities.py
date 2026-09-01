from __future__ import annotations

from hashlib import sha256

import pytest
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.v1_foundation import join_community
from pairpilot_orchestrator.v2_communities import (
    get_community_detail,
    query_community_agent,
)
from test_multi_user_platform import MemoryMultiUserStore


def principal(uid: str, email: str | None = None) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        uid=uid,
        email=email or f"{uid}@example.com",
        email_verified=True,
    )


async def seed_community(
    store: MemoryMultiUserStore,
    *,
    community_id: str = "community_builders",
    membership_type: str = "PUBLIC",
    **extra: object,
) -> None:
    await store.create(
        "communities",
        community_id,
        {
            "namespace": "production",
            "community_id": community_id,
            "name": "Production Agent Builders",
            "description": "A trusted place to form agent engineering teams.",
            "location": "Global",
            "membership_type": membership_type,
            "visibility": "PUBLIC" if membership_type == "PUBLIC" else "PRIVATE",
            "membership_policy": "PUBLIC_JOIN",
            "status": "ACTIVE",
            "rules": ["Do not publish contact details."],
            **extra,
        },
    )


async def seed_member(
    store: MemoryMultiUserStore,
    uid: str,
    *,
    community_id: str = "community_builders",
    role: str = "MEMBER",
    public: bool = True,
) -> None:
    agent_id = f"agent_{uid}"
    await store.create(
        "community_memberships",
        f"membership_{uid}",
        {
            "namespace": "production",
            "community_id": community_id,
            "owner_uid": uid,
            "role": role,
            "status": "ACTIVE",
        },
    )
    await store.create(
        "users",
        uid,
        {
            "namespace": "production",
            "uid": uid,
            "display_name": uid.title(),
            "email": f"{uid}@private.example",
            "account_status": "ACTIVE",
            "personal_agent_id": agent_id,
            "public_interests": ["agent reliability"],
            "protected_note": "never expose this",
        },
    )
    await store.create(
        "user_privacy_configs",
        uid,
        {"owner_uid": uid, "public_profile_visible": public},
    )
    await store.create(
        "personal_agents",
        agent_id,
        {
            "agent_id": agent_id,
            "owner_uid": uid,
            "display_name": f"{uid.title()} Agent",
            "private_instruction": "never expose this",
        },
    )


async def seed_public_post(store: MemoryMultiUserStore, uid: str) -> None:
    await store.create(
        "intent_posts",
        f"intent_{uid}",
        {
            "namespace": "production",
            "intent_id": f"intent_{uid}",
            "owner_uid": uid,
            "owner_agent_id": f"agent_{uid}",
            "community_id": "community_builders",
            "task_type": "HACKATHON_TEAMMATE",
            "public_title": "Find an agent reliability cofounder",
            "public_summary": "Build a production-grade evaluation loop.",
            "public_requirements": ["Python", "ADK"],
            "status": "OPEN",
            "capacity_remaining": 1,
            "private_constraint": "never expose this",
        },
    )


@pytest.mark.asyncio
async def test_public_overview_hides_member_directory_and_feed() -> None:
    store = MemoryMultiUserStore()
    await seed_community(store)
    await seed_member(store, "alice")
    await seed_public_post(store, "alice")

    detail = await get_community_detail(
        store, principal("visitor"), "community_builders"
    )

    assert detail["viewer"]["joined"] is False
    assert detail["counts"] == {"members": 1, "active_posts": 1, "active_plans": 0}
    assert detail["open_requests"] == {}
    assert detail["members"] == []
    assert "@private.example" not in str(detail).casefold()
    assert "never expose this" not in str(detail)


@pytest.mark.asyncio
async def test_joined_detail_exposes_only_public_member_post_and_room_projections() -> (
    None
):
    store = MemoryMultiUserStore()
    await seed_community(store)
    await seed_member(store, "viewer")
    await seed_member(store, "alice", role="MODERATOR")
    await seed_member(store, "private-person", public=False)
    await seed_member(store, "controlled-test", public=True)
    store.collections["users"]["controlled-test"]["display_name"] = (
        "Candidate A · Controlled test account"
    )
    await seed_public_post(store, "alice")
    await store.create(
        "coordination_rooms",
        "room_community",
        {
            "community_id": "community_builders",
            "room_id": "room_community",
            "title": "Public planning room",
            "visibility": "COMMUNITY",
            "private_transcript": "never expose this",
        },
    )
    await store.create(
        "coordination_rooms",
        "room_private",
        {
            "community_id": "community_builders",
            "room_id": "room_private",
            "visibility": "AGENTS_ONLY",
            "participant_uids": ["alice"],
        },
    )

    detail = await get_community_detail(
        store, principal("viewer"), "community_builders"
    )

    assert detail["viewer"]["joined"] is True
    assert [member["display_name"] for member in detail["members"]] == [
        "Viewer",
        "Alice",
    ]
    assert detail["moderators"] == ["Alice"]
    assert len(detail["open_requests"]["HACKATHON_TEAMMATE"]) == 1
    assert [room["room_id"] for room in detail["plans_and_rooms"]] == ["room_community"]
    serialized = str(detail).casefold()
    assert "@private.example" not in serialized
    assert "private_constraint" not in serialized
    assert "private_transcript" not in serialized


@pytest.mark.asyncio
async def test_community_agent_is_logical_scoped_and_cannot_read_private_stores() -> (
    None
):
    store = MemoryMultiUserStore()
    await seed_community(store)
    await seed_member(store, "viewer")
    await seed_member(store, "alice")
    await seed_public_post(store, "alice")
    await store.create(
        "memories",
        "memory_secret",
        {"owner_uid": "alice", "content": "secret memory phrase"},
    )
    await store.create(
        "conversation_messages",
        "message_secret",
        {"owner_uid": "alice", "content": "secret transcript phrase"},
    )

    answer = await query_community_agent(
        store,
        principal("viewer"),
        "community_builders",
        "Find open agent reliability requests",
    )

    assert answer["agent"]["role"] == "COMMUNITY_AGENT"
    assert answer["scope"] == "COMMUNITY_PUBLIC_AND_MEMBER_SAFE"
    assert answer["surfaced_posts"][0]["intent_id"] == "intent_alice"
    serialized = str(answer).casefold()
    assert "secret memory phrase" not in serialized
    assert "secret transcript phrase" not in serialized


@pytest.mark.asyncio
async def test_join_policy_fails_closed_for_all_membership_types() -> None:
    store = MemoryMultiUserStore()
    await seed_community(store, community_id="community_public")
    await seed_community(
        store,
        community_id="community_invite",
        membership_type="INVITE_LINK",
        invite_token_hash=sha256(b"valid-invite-token").hexdigest(),
    )
    await seed_community(
        store,
        community_id="community_approval",
        membership_type="APPROVAL_REQUIRED",
    )
    await seed_community(
        store,
        community_id="community_domain",
        membership_type="DOMAIN_VERIFIED",
        allowed_domains=["trusted.example"],
    )
    await seed_community(
        store, community_id="community_private", membership_type="PRIVATE"
    )

    assert (await join_community(store, principal("u1"), "community_public"))[
        "status"
    ] == "ACTIVE"
    with pytest.raises(PermissionError, match="COMMUNITY_INVITE_REQUIRED"):
        await join_community(store, principal("u2"), "community_invite")
    assert (
        await join_community(
            store,
            principal("u2"),
            "community_invite",
            invite_token="valid-invite-token",
        )
    )["status"] == "ACTIVE"
    assert (await join_community(store, principal("u3"), "community_approval"))[
        "status"
    ] == "PENDING"
    with pytest.raises(PermissionError, match="COMMUNITY_DOMAIN_REQUIRED"):
        await join_community(store, principal("u4"), "community_domain")
    assert (
        await join_community(
            store,
            principal("u5", "u5@trusted.example"),
            "community_domain",
        )
    )["status"] == "ACTIVE"
    with pytest.raises(PermissionError, match="COMMUNITY_PRIVATE"):
        await join_community(store, principal("u6"), "community_private")


@pytest.mark.asyncio
async def test_moderator_capability_is_derived_server_side_from_active_role() -> None:
    store = MemoryMultiUserStore()
    await seed_community(store)
    await seed_member(store, "moderator", role="MODERATOR")
    await seed_member(store, "member", role="MEMBER")

    moderator = await get_community_detail(
        store, principal("moderator"), "community_builders"
    )
    member = await get_community_detail(
        store, principal("member"), "community_builders"
    )

    assert moderator["viewer"]["can_moderate"] is True
    assert member["viewer"]["can_moderate"] is False
