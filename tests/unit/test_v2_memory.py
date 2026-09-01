from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.v2_memory import (
    apply_memory_action,
    get_memory_detail,
    list_memory_workspace,
    retrieve_memory_context,
)
from test_multi_user_platform import MemoryMultiUserStore


def principal(uid: str = "owner") -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        uid=uid, email=f"{uid}@example.com", email_verified=True
    )


async def memory(
    store: MemoryMultiUserStore,
    memory_id: str,
    *,
    status: str,
    memory_type: str,
    scope: str,
    content: str,
    **extra: object,
) -> None:
    await store.create(
        "memories",
        memory_id,
        {
            "schema_version": 3,
            "namespace": "production",
            "memory_id": memory_id,
            "owner_uid": "owner",
            "memory_type": memory_type,
            "scope": scope,
            "content": content,
            "status": status,
            "confirmation_status": status,
            "created_at": datetime.now(UTC),
            **extra,
        },
    )


@pytest.mark.asyncio
async def test_proposed_and_working_belief_never_enter_agent_context() -> None:
    store = MemoryMultiUserStore()
    await memory(
        store,
        "memory_proposed",
        status="PROPOSED",
        memory_type="CONFIRMED_USER_MEMORY",
        scope="GLOBAL",
        content="Likes early starts",
    )
    await memory(
        store,
        "memory_belief",
        status="CONFIRMED",
        memory_type="WORKING_BELIEF",
        scope="GLOBAL",
        content="Might like early starts",
    )
    assert (
        await retrieve_memory_context(store, principal(), task_id=None, purpose="TEST")
        == []
    )
    assert not store.collections["memory_usage_events"]


@pytest.mark.asyncio
async def test_scope_and_task_exception_override_are_enforced_and_audited() -> None:
    store = MemoryMultiUserStore()
    await store.create(
        "task_workspaces",
        "task_trip",
        {
            "namespace": "production",
            "task_id": "task_trip",
            "owner_uid": "owner",
            "task_type": "EVENT_BUDDY",
        },
    )
    await memory(
        store,
        "memory_global",
        status="CONFIRMED",
        memory_type="CONFIRMED_USER_MEMORY",
        scope="GLOBAL",
        content="Usually prefers early mornings",
        topic_key="start_time",
    )
    await memory(
        store,
        "memory_exception",
        status="CONFIRMED",
        memory_type="TASK_MEMORY",
        scope="TASK:task_trip",
        content="For this event, prefers a late start",
        topic_key="start_time",
    )
    await memory(
        store,
        "memory_other_task",
        status="CONFIRMED",
        memory_type="TASK_MEMORY",
        scope="TASK:task_other",
        content="Other task detail",
    )
    context = await retrieve_memory_context(
        store, principal(), task_id="task_trip", purpose="PERSONAL_AGENT_CONTEXT"
    )
    assert [item["memory_id"] for item in context] == ["memory_exception"]
    assert context[0]["usage_id"].startswith("memory_usage_")
    assert len(store.collections["memory_usage_events"]) == 1


@pytest.mark.asyncio
async def test_episodic_memory_does_not_become_global_preference() -> None:
    store = MemoryMultiUserStore()
    await memory(
        store,
        "memory_episode",
        status="CONFIRMED",
        memory_type="EPISODIC_MEMORY",
        scope="GLOBAL",
        content="One plan happened",
    )
    assert (
        await retrieve_memory_context(store, principal(), task_id=None, purpose="TEST")
        == []
    )


@pytest.mark.asyncio
async def test_conflicting_confirmation_creates_review_decision() -> None:
    store = MemoryMultiUserStore()
    await memory(
        store,
        "memory_confirmed",
        status="CONFIRMED",
        memory_type="CONFIRMED_USER_MEMORY",
        scope="GLOBAL",
        content="Prefers early mornings",
    )
    await memory(
        store,
        "memory_conflict",
        status="PROPOSED",
        memory_type="CONFIRMED_USER_MEMORY",
        scope="GLOBAL",
        content="Prefers sleeping in",
        contradicts_memory_ids=["memory_confirmed"],
    )
    with pytest.raises(ValueError, match="requires review"):
        await apply_memory_action(
            store,
            principal(),
            memory_id="memory_conflict",
            action="CONFIRM",
            content=None,
            scope=None,
        )
    persisted = await store.get("memories", "memory_conflict")
    assert persisted is not None
    assert persisted["status"] == "PROPOSED"
    assert persisted["confirmation_status"] == "NEEDS_REVIEW"
    assert len(store.collections["decisions"]) == 1


@pytest.mark.asyncio
async def test_workspace_detail_and_disable_lifecycle_explain_usage() -> None:
    store = MemoryMultiUserStore()
    await memory(
        store,
        "memory_pref",
        status="CONFIRMED",
        memory_type="CONFIRMED_USER_MEMORY",
        scope="PREFERENCES",
        content="Prefers flexible pacing",
        source="USER_CONFIRMED",
        confidence="AUTHORITATIVE_OWNER_CONFIRMATION",
    )
    await retrieve_memory_context(
        store, principal(), task_id=None, purpose="CANDIDATE_RANKING"
    )
    workspace = await list_memory_workspace(store, principal())
    detail = await get_memory_detail(store, principal(), "memory_pref")
    assert workspace["groups"]["RECENTLY_USED"][0]["usage_count"] == 1
    assert detail["why_this_was_used"][0]["usage_id"].startswith("memory_usage_")
    disabled = await apply_memory_action(
        store,
        principal(),
        memory_id="memory_pref",
        action="TEMPORARILY_DISABLE",
        content=None,
        scope=None,
    )
    assert disabled["disabled"] is True
    assert (
        await retrieve_memory_context(
            store, principal(), task_id=None, purpose="TEST_AFTER_DISABLE"
        )
        == []
    )
    enabled = await apply_memory_action(
        store,
        principal(),
        memory_id="memory_pref",
        action="ENABLE",
        content=None,
        scope=None,
    )
    assert enabled["disabled"] is False
