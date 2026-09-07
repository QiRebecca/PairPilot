from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.multi_user_platform import provision_user
from pairpilot_orchestrator.personal_agent_chat import _directive
from pairpilot_orchestrator.v2_product_glue import (
    autonomy_level_for,
    get_autonomy_center,
    list_decision_inbox,
    list_notifications,
    mark_all_notifications_read,
    resolve_decision,
    set_notification_state,
    update_autonomy_policy,
    update_notification_settings,
)
from test_multi_user_platform import MemoryMultiUserStore


def principal(uid: str = "owner") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        uid=uid, email=f"{uid}@example.com", email_verified=True
    )


@pytest.mark.asyncio
async def test_decision_inbox_is_owner_scoped_routed_and_rejects_change() -> None:
    store = MemoryMultiUserStore()
    await store.create(
        "decisions",
        "decision_change",
        {
            "namespace": "production",
            "decision_id": "decision_change",
            "owner_uid": "owner",
            "match_id": "match_pair",
            "change_id": "change_pair",
            "version": 3,
            "type": "APPROVE_MATCH_CHANGE",
            "status": "OPEN",
            "title": "Review change",
            "created_at": datetime.now(UTC),
        },
    )
    await store.create(
        "match_change_proposals",
        "change_pair",
        {
            "namespace": "production",
            "change_id": "change_pair",
            "match_id": "match_pair",
            "version": 3,
            "status": "AWAITING_APPROVALS",
        },
    )
    await store.create(
        "decisions",
        "decision_other",
        {
            "namespace": "production",
            "decision_id": "decision_other",
            "owner_uid": "other",
            "type": "CONFIRM_MEMORY",
            "status": "OPEN",
        },
    )
    inbox = await list_decision_inbox(store, principal())
    assert inbox["open_count"] == 1
    assert inbox["open"][0]["type"] == "REVIEW_MATCH_CHANGE"
    assert inbox["open"][0]["entity_route"] == "/app/matches/match_pair"
    assert inbox["open"][0]["required_confirmation"] == "APPROVE CHANGE VERSION 3"
    rejected = await resolve_decision(
        store,
        principal(),
        decision_id="decision_change",
        outcome="REJECT",
        confirmation=None,
    )
    assert rejected["status"] == "REJECTED"
    change = await store.get("match_change_proposals", "change_pair")
    assert change is not None
    assert change["status"] == "REJECTED"


@pytest.mark.asyncio
async def test_notifications_are_actionable_and_owner_state_isolated() -> None:
    store = MemoryMultiUserStore()
    for notification_id, owner_uid in (
        ("notification_one", "owner"),
        ("notification_two", "other"),
    ):
        await store.create(
            "notifications",
            notification_id,
            {
                "namespace": "production",
                "notification_id": notification_id,
                "owner_uid": owner_uid,
                "type": "MATCH_CANCELLED",
                "title": "Plan cancelled",
                "body": "Review backup options.",
                "entity_ids": ["match_pair"],
                "status": "UNREAD",
                "created_at": datetime.now(UTC),
            },
        )
    payload = await list_notifications(store, principal())
    assert payload["unread_count"] == 1
    assert payload["notifications"][0]["category"] == "MATCH_UPDATE"
    assert payload["notifications"][0]["entity_route"] == "/app/matches/match_pair"
    await set_notification_state(
        store,
        principal(),
        notification_id="notification_one",
        state="READ",
    )
    assert (await mark_all_notifications_read(store, principal()))["updated"] == 0


@pytest.mark.asyncio
async def test_saved_search_notification_routes_to_public_post_detail() -> None:
    store = MemoryMultiUserStore()
    await store.create(
        "notifications",
        "notification_search_match",
        {
            "namespace": "production",
            "notification_id": "notification_search_match",
            "owner_uid": "owner",
            "type": "SAVED_SEARCH_MATCH",
            "title": "A monitored Post is available",
            "body": "Public Post title",
            "entity_ids": ["intent_public_match"],
            "status": "UNREAD",
            "created_at": datetime.now(UTC),
        },
    )

    payload = await list_notifications(store, principal())

    notification = payload["notifications"][0]
    assert notification["category"] == "CANDIDATE_CHANGE"
    assert notification["entity_route"] == "/app/posts/intent_public_match"
    with pytest.raises(LookupError):
        await set_notification_state(
            store,
            principal(),
            notification_id="notification_two",
            state="READ",
        )


@pytest.mark.asyncio
async def test_notification_settings_do_not_fake_browser_push_registration() -> None:
    store = MemoryMultiUserStore()
    updated = await update_notification_settings(
        store,
        principal(),
        values={
            "in_app_enabled": True,
            "browser_push_enabled": True,
            "meaningful_events_only": True,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "08:00",
        },
    )
    assert updated["browser_push_enabled"] is False
    assert updated["browser_push_status"] == "CONSENT_NOT_REGISTERED"


@pytest.mark.asyncio
async def test_action_specific_autonomy_enforces_global_and_task_policies() -> None:
    store = MemoryMultiUserStore()
    user = principal()
    await provision_user(store, user)
    await store.create(
        "task_workspaces",
        "task_event",
        {
            "namespace": "production",
            "task_id": "task_event",
            "owner_uid": user.uid,
            "task_type": "EVENT_BUDDY",
        },
    )
    center = await get_autonomy_center(store, user)
    assert center["action_levels"]["SHARE_PROTECTED_INFORMATION"] == "NEVER"
    assert center["action_levels"]["APPROVE_FINAL_COMMITMENT"] == "ASK_FIRST"
    await update_autonomy_policy(
        store,
        user,
        action_levels={"PUBLISH_POST": "AUTOMATIC"},
        task_id=None,
    )
    await update_autonomy_policy(
        store,
        user,
        action_levels={"PUBLISH_POST": "NEVER"},
        task_id="task_event",
    )
    assert (
        await autonomy_level_for(
            store, owner_uid=user.uid, action="PUBLISH_POST", task_id=None
        )
        == "AUTOMATIC"
    )
    assert (
        await autonomy_level_for(
            store, owner_uid=user.uid, action="PUBLISH_POST", task_id="task_event"
        )
        == "NEVER"
    )
    with pytest.raises(ValueError, match="cannot become automatic"):
        await update_autonomy_policy(
            store,
            user,
            action_levels={"APPROVE_FINAL_COMMITMENT": "AUTOMATIC"},
            task_id=None,
        )
    assert len(store.collections["autonomy_activity_events"]) == 2


@pytest.mark.asyncio
async def test_model_directive_cannot_reference_unauthorized_private_entity() -> None:
    store = MemoryMultiUserStore()
    await store.create(
        "memories",
        "memory_other",
        {
            "namespace": "production",
            "memory_id": "memory_other",
            "owner_uid": "other",
            "content": "Private",
        },
    )
    with pytest.raises(PermissionError, match="not owner-authorized"):
        await _directive(
            store,
            principal(),
            conversation_id="user:owner:global",
            action="SHOW_MEMORY",
            entity_ids=["memory_other"],
            explanation="Attempted unauthorized display",
        )
    assert not store.collections["presentation_directives"]
