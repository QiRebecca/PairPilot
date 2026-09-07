from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

import pytest
from pairpilot_orchestrator import web
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.v2_marketplace import (
    create_saved_search,
    evaluate_saved_search,
    evaluate_saved_searches_for_post,
    get_post_detail,
    save_post,
    search_marketplace,
    unsave_post,
)
from pairpilot_schemas import ExploreSearchInput, SaveSearchInput
from test_multi_user_platform import MemoryMultiUserStore


def principal(uid: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        uid=uid,
        email=f"{uid}@example.com",
        email_verified=True,
    )


async def seed_membership(
    store: MemoryMultiUserStore, uid: str, community_id: str = "community_ai"
) -> None:
    await store.create(
        "community_memberships",
        f"membership-{uid}",
        {
            "owner_uid": uid,
            "community_id": community_id,
            "status": "ACTIVE",
            "namespace": "production",
        },
    )


async def seed_post(
    store: MemoryMultiUserStore,
    *,
    intent_id: str,
    owner_uid: str,
    owner_agent_id: str,
    status: str = "OPEN",
    community_id: str = "community_ai",
    title: str = "Find an AI conference dinner partner",
    private_marker: str = "must-never-leak",
    public_display_name: str | None = None,
) -> None:
    await store.create(
        "intent_posts",
        intent_id,
        {
            "schema_version": 3,
            "namespace": "production",
            "intent_id": intent_id,
            "owner_uid": owner_uid,
            "owner_agent_id": owner_agent_id,
            "community_id": community_id,
            "task_type": "MEAL_COMPANION",
            "public_display_name": public_display_name or owner_uid,
            "public_title": title,
            "public_summary": "Dinner after the keynote to discuss agent systems.",
            "public_constraints": {
                "location": "Seoul",
                "date_start": "2026-09-10",
                "date_end": "2026-09-10",
            },
            "public_requirements": ["AI agents", "split bill"],
            "capacity_remaining": 1,
            "status": status,
            "updated_at": datetime.now(UTC),
            "private_marker": private_marker,
        },
    )


@pytest.mark.asyncio
async def test_search_is_server_scoped_ranked_and_public_only() -> None:
    store = MemoryMultiUserStore()
    await seed_membership(store, "viewer")
    await seed_post(
        store,
        intent_id="intent_visible",
        owner_uid="peer-a",
        owner_agent_id="agent_peer_a",
    )
    await seed_post(
        store,
        intent_id="intent_other_community",
        owner_uid="peer-b",
        owner_agent_id="agent_peer_b",
        community_id="community_other",
    )
    await seed_post(
        store,
        intent_id="intent_paused",
        owner_uid="peer-c",
        owner_agent_id="agent_peer_c",
        status="PAUSED",
    )

    result = await search_marketplace(
        store,
        principal("viewer"),
        ExploreSearchInput(query="keynote agent dinner", view="LATEST"),
    )

    assert result["count"] == 1
    item = result["items"][0]
    assert item["intent_id"] == "intent_visible"
    assert item["relevance_score"] > 0.2
    assert item["surfaced_reasons"]
    assert "private_marker" not in item
    assert result["retrieval"]["semantic_vector"] is False


@pytest.mark.asyncio
async def test_blocked_owner_is_removed_from_search_and_detail() -> None:
    store = MemoryMultiUserStore()
    await seed_membership(store, "viewer")
    await seed_post(
        store,
        intent_id="intent_blocked",
        owner_uid="peer-a",
        owner_agent_id="agent_peer_a",
    )
    await store.create(
        "blocks",
        "block-a",
        {
            "blocker_uid": "viewer",
            "blocked_uid": "peer-a",
            "status": "ACTIVE",
        },
    )

    result = await search_marketplace(
        store, principal("viewer"), ExploreSearchInput(view="LATEST")
    )
    assert result["items"] == []
    with pytest.raises(LookupError):
        await get_post_detail(store, principal("viewer"), "intent_blocked")


@pytest.mark.asyncio
async def test_my_posts_includes_paused_but_public_detail_does_not() -> None:
    store = MemoryMultiUserStore()
    await seed_membership(store, "owner")
    await seed_membership(store, "viewer")
    await seed_post(
        store,
        intent_id="intent_paused",
        owner_uid="owner",
        owner_agent_id="agent_owner",
        status="PAUSED",
    )

    own = await search_marketplace(
        store, principal("owner"), ExploreSearchInput(view="MY_POSTS")
    )
    assert own["items"][0]["status"] == "PAUSED"
    detail = await get_post_detail(store, principal("owner"), "intent_paused")
    assert detail["post"]["owned_by_viewer"] is True
    with pytest.raises(LookupError):
        await get_post_detail(store, principal("viewer"), "intent_paused")


@pytest.mark.asyncio
async def test_saved_post_lifecycle_is_idempotent_and_owner_scoped() -> None:
    store = MemoryMultiUserStore()
    await seed_membership(store, "viewer")
    await seed_post(
        store,
        intent_id="intent_saved",
        owner_uid="peer-a",
        owner_agent_id="agent_peer_a",
    )

    first = await save_post(
        store, principal("viewer"), intent_id="intent_saved", task_id=None
    )
    second = await save_post(
        store, principal("viewer"), intent_id="intent_saved", task_id=None
    )
    assert first["saved_post_id"] == second["saved_post_id"]
    saved = await search_marketplace(
        store, principal("viewer"), ExploreSearchInput(view="SAVED")
    )
    assert [item["intent_id"] for item in saved["items"]] == ["intent_saved"]

    await unsave_post(store, principal("viewer"), intent_id="intent_saved")
    after = await search_marketplace(
        store, principal("viewer"), ExploreSearchInput(view="SAVED")
    )
    assert after["items"] == []

    detail_after_remove = await get_post_detail(
        store, principal("viewer"), "intent_saved"
    )
    assert detail_after_remove["saved"] is False

    await save_post(
        store, principal("viewer"), intent_id="intent_saved", task_id=None
    )
    latest = await search_marketplace(
        store, principal("viewer"), ExploreSearchInput(view="LATEST")
    )
    assert latest["items"][0]["saved"] is True
    saved_again = await search_marketplace(
        store, principal("viewer"), ExploreSearchInput(view="SAVED")
    )
    assert [item["intent_id"] for item in saved_again["items"]] == [
        "intent_saved"
    ]


@pytest.mark.asyncio
async def test_monitored_saved_search_is_persisted_and_emits_event() -> None:
    store = MemoryMultiUserStore()
    await seed_membership(store, "viewer")
    saved = await create_saved_search(
        store,
        principal("viewer"),
        SaveSearchInput(
            name="Agent systems dinner",
            search=ExploreSearchInput(
                query="agent systems dinner",
                view="FROM_COMMUNITIES",
                community_id="community_ai",
            ),
            monitor_enabled=True,
        ),
    )
    assert saved["monitor_status"] == "ACTIVE"
    assert saved["notification_sensitivity"] == "MEANINGFUL"
    events = list(store.collections["events"].values())
    assert len(events) == 1
    assert events[0]["eventType"] == "marketplace.saved_search.created.v2"
    assert "agent systems dinner" not in str(events[0]["payload"]).casefold()


@pytest.mark.asyncio
async def test_saved_search_monitor_notifies_once_with_public_scoped_data() -> None:
    store = MemoryMultiUserStore()
    await seed_membership(store, "viewer")
    saved = await create_saved_search(
        store,
        principal("viewer"),
        SaveSearchInput(
            name="Agent systems dinner",
            search=ExploreSearchInput(
                query="agent systems dinner",
                view="FROM_COMMUNITIES",
                community_id="community_ai",
            ),
            monitor_enabled=True,
            notification_sensitivity="MEANINGFUL",
        ),
    )
    await seed_post(
        store,
        intent_id="intent_monitor_match",
        owner_uid="peer-monitor",
        owner_agent_id="agent_peer_monitor",
        private_marker="private-budget-must-not-leak",
    )

    first = await evaluate_saved_searches_for_post(store, "intent_monitor_match")
    duplicate = await evaluate_saved_searches_for_post(
        store, "intent_monitor_match"
    )
    current = await evaluate_saved_search(store, str(saved["saved_search_id"]))

    assert first == {"searches_evaluated": 1, "new_matches": 1}
    assert duplicate == {"searches_evaluated": 1, "new_matches": 0}
    assert current == {"posts_evaluated": 1, "new_matches": 0}
    assert len(store.collections["saved_search_hits"]) == 1
    notifications = list(store.collections["notifications"].values())
    assert len(notifications) == 1
    assert notifications[0]["type"] == "SAVED_SEARCH_MATCH"
    assert notifications[0]["entity_ids"] == ["intent_monitor_match"]
    assert "private-budget-must-not-leak" not in str(notifications)


@pytest.mark.asyncio
async def test_saved_search_monitor_respects_community_scope() -> None:
    store = MemoryMultiUserStore()
    await seed_membership(store, "viewer", "community_ai")
    await create_saved_search(
        store,
        principal("viewer"),
        SaveSearchInput(
            name="Agent dinner anywhere joined",
            search=ExploreSearchInput(
                query="agent dinner",
                view="FROM_COMMUNITIES",
            ),
            monitor_enabled=True,
            notification_sensitivity="HIGH",
        ),
    )
    await seed_post(
        store,
        intent_id="intent_outside_scope",
        owner_uid="outside-peer",
        owner_agent_id="agent_outside_peer",
        community_id="community_private_other",
    )

    result = await evaluate_saved_searches_for_post(
        store, "intent_outside_scope"
    )

    assert result == {"searches_evaluated": 1, "new_matches": 0}
    assert store.collections["saved_search_hits"] == {}
    assert store.collections["notifications"] == {}


@pytest.mark.asyncio
async def test_saved_search_pubsub_event_runs_the_monitor(monkeypatch) -> None:
    store = MemoryMultiUserStore()
    await seed_membership(store, "viewer")
    saved = await create_saved_search(
        store,
        principal("viewer"),
        SaveSearchInput(
            name="Agent systems dinner",
            search=ExploreSearchInput(
                query="agent systems dinner",
                view="FROM_COMMUNITIES",
                community_id="community_ai",
            ),
            monitor_enabled=True,
        ),
    )
    await seed_post(
        store,
        intent_id="intent_existing_monitor_match",
        owner_uid="peer-existing",
        owner_agent_id="agent_peer_existing",
    )
    monkeypatch.setattr(web, "_store", lambda: store)
    event = {
        "eventType": "marketplace.saved_search.created.v2",
        "payload": {"savedSearchId": saved["saved_search_id"]},
    }
    body = web.PubSubPushBody(
        message=web.PubSubPushMessage(
            data=base64.b64encode(json.dumps(event).encode()).decode()
        )
    )

    result = await web.internal_event_worker(body, "authenticated-worker")

    assert result["status"] == "SAVED_SEARCH_EVALUATED"
    assert result["result"]["new_matches"] == 1


@pytest.mark.asyncio
async def test_legacy_task_type_fails_as_validation_not_internal_error() -> None:
    store = MemoryMultiUserStore()
    await store.create(
        "task_workspaces",
        "task_legacy",
        {
            "task_id": "task_legacy",
            "owner_uid": "viewer",
            "task_type": "peer_coordination",
        },
    )
    with pytest.raises(ValueError, match="LEGACY_TASK_TYPE_REQUIRES_MIGRATION"):
        await search_marketplace(
            store,
            principal("viewer"),
            ExploreSearchInput(view="FOR_YOUR_REQUESTS", task_id="task_legacy"),
        )


@pytest.mark.asyncio
async def test_explicit_controlled_demo_posts_never_enter_real_marketplace() -> None:
    store = MemoryMultiUserStore()
    await seed_membership(store, "viewer")
    await seed_post(
        store,
        intent_id="intent_demo",
        owner_uid="controlled-user",
        owner_agent_id="agent_controlled",
        title="Controlled demo: founder coffee — C",
    )
    result = await search_marketplace(
        store, principal("viewer"), ExploreSearchInput(view="LATEST")
    )
    assert result["items"] == []
    with pytest.raises(LookupError):
        await get_post_detail(store, principal("viewer"), "intent_demo")

    await seed_post(
        store,
        intent_id="intent_demo_profile",
        owner_uid="controlled-profile",
        owner_agent_id="agent_controlled_profile",
        title="Late security reviewer",
        public_display_name="Chloe — Controlled Demo Participant",
    )
    second = await search_marketplace(
        store, principal("viewer"), ExploreSearchInput(view="LATEST")
    )
    assert second["items"] == []
