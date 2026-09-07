from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pairpilot_orchestrator import web
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.firestore_session_service import FirestoreSessionService
from pairpilot_orchestrator.generic_agent_runtime import (
    AgentRuntimeError,
    consume_daily_agent_turns,
    load_personal_agent,
    process_published_intent,
)
from pairpilot_orchestrator.infrastructure.google_cloud import decode_fields
from pairpilot_orchestrator.multi_user_agent import public_agent_projection
from pairpilot_orchestrator.multi_user_commit import (
    MultiUserCommitError,
    approve_multi_user_proposal,
    commit_dual_approved_match,
)
from pairpilot_orchestrator.multi_user_platform import (
    agent_id_for_uid,
    build_user_bootstrap,
    complete_onboarding,
    create_user_task,
    provision_user,
    publish_user_post,
    set_user_post_status,
)
from pairpilot_orchestrator.personal_agent_chat import (
    _build_tools,
    _scoped_context,
    resolve_task_intent_type,
)
from pairpilot_orchestrator.v1_candidate_pool import (
    record_candidate_exchange,
    set_candidate_state,
)
from pairpilot_orchestrator.v1_foundation import (
    DEFAULT_COMMUNITY_ID,
    memory_is_confirmed,
    update_memory_lifecycle,
)
from pairpilot_orchestrator.v1_operations import build_admin_dashboard
from pairpilot_orchestrator.v1_reconciliation import (
    reconcile_candidate_availability,
    reconcile_open_posts,
)
from pairpilot_orchestrator.v1_relationships import (
    list_match_contact_cards,
    offer_contact_card,
    revoke_contact_card,
    submit_outcome_check_in,
)
from pairpilot_schemas import (
    ContactCardInput,
    CreateUserTaskInput,
    OnboardingInput,
    OutcomeCheckInInput,
)


class MemoryMultiUserStore:
    def __init__(self) -> None:
        self.collections: defaultdict[str, dict[str, dict[str, Any]]] = defaultdict(
            dict
        )
        self.version = 0

    def _stamp(self, data: Mapping[str, Any]) -> dict[str, Any]:
        self.version += 1
        return {**dict(data), "_updateTime": f"version-{self.version}"}

    def document_name(self, collection: str, document_id: str) -> str:
        return f"projects/test/databases/(default)/documents/{collection}/{document_id}"

    async def get(self, collection: str, document_id: str) -> dict[str, Any] | None:
        item = self.collections[collection].get(document_id)
        return dict(item) if item is not None else None

    async def query_documents(
        self,
        collection: str,
        *,
        filters: list[tuple[str, str, Any]],
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        def matches(item: Mapping[str, Any]) -> bool:
            for field, operator, value in filters:
                if operator == "EQUAL" and item.get(field) != value:
                    return False
                if operator == "ARRAY_CONTAINS" and value not in item.get(field, []):
                    return False
            return True

        return [
            {**dict(item), "_id": document_id}
            for document_id, item in list(self.collections[collection].items())
            if matches(item)
        ][:limit]

    async def create(
        self, collection: str, document_id: str, data: Mapping[str, Any]
    ) -> bool:
        if document_id in self.collections[collection]:
            return False
        self.collections[collection][document_id] = self._stamp(data)
        return True

    async def upsert(
        self, collection: str, document_id: str, data: Mapping[str, Any]
    ) -> dict[str, Any]:
        stamped = self._stamp(data)
        self.collections[collection][document_id] = stamped
        return dict(stamped)

    async def commit_writes(self, writes: list[dict[str, Any]]) -> dict[str, Any]:
        pending: list[tuple[str, str, dict[str, Any]]] = []
        for write in writes:
            update = write["update"]
            path = str(update["name"]).split("/documents/", 1)[1]
            collection, document_id = path.split("/", 1)
            current = self.collections[collection].get(document_id)
            condition = write.get("currentDocument", {})
            if condition.get("exists") is False and current is not None:
                raise RuntimeError("already exists")
            if condition.get("updateTime") and (
                current is None or current.get("_updateTime") != condition["updateTime"]
            ):
                raise RuntimeError("precondition failed")
            pending.append(
                (collection, document_id, decode_fields(update.get("fields", {})))
            )
        for collection, document_id, data in pending:
            self.collections[collection][document_id] = self._stamp(data)
        return {"writeResults": len(pending)}

    async def write_event(
        self,
        *,
        event_type: str,
        run_id: str,
        producer: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
        publish_immediately: bool = True,
    ) -> dict[str, Any]:
        event_id = f"event-{len(self.collections['events']) + 1}"
        await self.create(
            "events",
            event_id,
            {
                "eventType": event_type,
                "runId": run_id,
                "producer": producer,
                "payload": dict(payload),
                "idempotencyKey": idempotency_key,
                "published": publish_immediately,
            },
        )
        return {"event_id": event_id}


class ApiVerifier:
    async def verify(self, token: str) -> AuthenticatedPrincipal:
        if token == "user-a":
            return principal("uid-a")
        if token == "user-b":
            return principal("uid-b")
        raise RuntimeError("unexpected test token")


def principal(uid: str, *, verified: bool = True) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        uid=uid,
        email=f"{uid}@example.test",
        email_verified=verified,
    )


def onboarding(name: str) -> OnboardingInput:
    return OnboardingInput(
        display_name=name,
        timezone="Asia/Shanghai",
        general_location="Shanghai",
        language="English",
        adult_confirmed=True,
        public_profile_visible=True,
        default_autonomy_mode="COPILOT",
        public_sharing_policy="Only reviewed public post fields.",
        agent_sharing_policy="Minimum task-scoped evidence.",
        always_ask_policy="Always ask before commitment.",
    )


def task_input(title: str) -> CreateUserTaskInput:
    return CreateUserTaskInput(
        title=title,
        task_type="conference_room_share",
        goal=f"{title}: find a compatible conference roommate with quiet nights.",
        event="ICML",
        location="Seoul",
        date_start=date(2026, 7, 6),
        date_end=date(2026, 7, 10),
        public_requirements=["Adult ICML attendee"],
        maximum_additional_cost_usd=70,
        partial_date_overlap_allowed=True,
    )


def _agent_messages_for_test() -> dict[str, str]:
    return {
        agent_id_for_uid("uid-a"): "I accept a reversible introduction.",
        agent_id_for_uid("uid-b"): "I also accept a reversible introduction.",
    }


@pytest.mark.parametrize(
    ("requested", "event", "goal", "expected"),
    [
        ("EVENT_BUDDY", "Hong Kong Disneyland", "Find a photo buddy", "EVENT_BUDDY"),
        ("peer_coordination", "香港迪士尼", "找女生一起拍照游玩", "EVENT_BUDDY"),
        ("", "ICML hotel", "Find a quiet roommate", "ROOM_SHARE"),
        ("", "Conference dinner", "Find a dinner companion", "MEAL_COMPANION"),
        ("", "Coffee", "Meet for a coffee chat", "COFFEE_CHAT"),
        ("", "OpenAI Build Week", "找黑客松队友组队", "HACKATHON_TEAMMATE"),
    ],
)
def test_personal_agent_resolves_all_v1_intent_types(
    requested: str, event: str, goal: str, expected: str
) -> None:
    assert resolve_task_intent_type(requested, event=event, goal=goal) == expected


@pytest.mark.asyncio
async def test_personal_agent_global_context_treats_explicit_null_as_unscoped() -> None:
    store = MemoryMultiUserStore()
    user = principal("uid-a")
    await provision_user(store, user)

    context = await _scoped_context(
        store,
        user,
        {
            "conversation_id": "user:uid-a:global",
            "kind": "GLOBAL_PERSONAL_AGENT",
            "task_id": None,
        },
    )

    assert context["conversationKind"] == "GLOBAL_PERSONAL_AGENT"
    assert "selectedTask" not in context


@pytest.mark.asyncio
async def test_personal_agent_task_tool_no_longer_uses_legacy_type() -> None:
    store = MemoryMultiUserStore()
    user = principal("uid-event")
    await provision_user(store, user)
    await complete_onboarding(store, user, onboarding("Event User"))
    conversation = await store.get("conversations", "user:uid-event:global")
    assert conversation is not None
    tool = _build_tools(
        store,
        user,
        conversation,
        authorizing_user_content="I want a photo buddy for Disneyland on September 10.",
    )[0]
    result = await tool(
        title="Disney photo buddy",
        goal="Find an adult companion for Disneyland photos and rides.",
        event="Hong Kong Disneyland",
        location="Hong Kong",
        date_start="2026-09-10",
        date_end="2026-09-10",
        public_requirements=["Adult", "Enjoys photos"],
    )
    created = store.collections["task_workspaces"][str(result["task_id"])]
    assert created["task_type"] == "EVENT_BUDDY"


@pytest.mark.asyncio
async def test_personal_agent_task_tool_uses_users_active_community() -> None:
    store = MemoryMultiUserStore()
    user = principal("uid-community")
    await provision_user(store, user)
    await complete_onboarding(
        store,
        user,
        onboarding("Community User").model_copy(
            update={"community_ids": ["community_agent_builders"]}
        ),
    )
    conversation = await store.get("conversations", "user:uid-community:global")
    assert conversation is not None
    tool = _build_tools(
        store,
        user,
        conversation,
        authorizing_user_content="Find an agent builder for a production review.",
    )[0]

    result = await tool(
        title="Agent production review",
        goal="Find an adult agent builder for a hands-on production readiness review.",
        event="Agentic Systems Review",
        location="Remote",
        date_start="2026-09-10",
        date_end="2026-09-10",
        public_requirements=["Adult AI builder", "Google ADK experience"],
    )

    created = store.collections["task_workspaces"][str(result["task_id"])]
    assert created["community_id"] == "community_agent_builders"


@pytest.mark.asyncio
async def test_reconciliation_rotates_fairly_across_open_posts(monkeypatch) -> None:
    class StrictLimitStore(MemoryMultiUserStore):
        async def query_documents(self, collection, *, filters, limit=100):
            assert 1 <= limit <= 100
            return await super().query_documents(
                collection, filters=filters, limit=limit
            )

    store = StrictLimitStore()
    attempted: list[str] = []
    for index in range(5):
        task_id = f"task-fair-{index}"
        intent_id = f"intent-fair-{index}"
        await store.create(
            "task_workspaces",
            task_id,
            {
                "namespace": "production",
                "task_id": task_id,
                "contact_count": 0,
                "status": "SEARCHING",
            },
        )
        await store.create(
            "intent_posts",
            intent_id,
            {
                "namespace": "production",
                "intent_id": intent_id,
                "task_id": task_id,
                "status": "OPEN",
                "published_at": datetime(2026, 9, 1, 0, index, tzinfo=UTC),
            },
        )

    async def fake_process(_store, intent_id):
        attempted.append(intent_id)
        return {"contacted": 0}

    monkeypatch.setattr(
        "pairpilot_orchestrator.v1_reconciliation.process_candidate_pool_event",
        fake_process,
    )
    assert (await reconcile_open_posts(store))["posts_attempted"] == 3
    assert (await reconcile_open_posts(store))["posts_attempted"] == 3
    assert attempted[:3] == ["intent-fair-0", "intent-fair-1", "intent-fair-2"]
    assert attempted[3:5] == ["intent-fair-3", "intent-fair-4"]


@pytest.mark.asyncio
async def test_provisioning_is_idempotent_and_creates_one_agent() -> None:
    store = MemoryMultiUserStore()
    user = principal("uid-a", verified=False)
    first = await provision_user(store, user, now=datetime(2026, 8, 29, tzinfo=UTC))
    second = await provision_user(store, user, now=datetime(2026, 8, 29, tzinfo=UTC))
    assert first["personal_agent_id"] == agent_id_for_uid("uid-a")
    assert second["personal_agent_id"] == first["personal_agent_id"]
    assert len(store.collections["users"]) == 1
    assert len(store.collections["personal_agents"]) == 1
    assert len(store.collections["conversations"]) == 1


@pytest.mark.asyncio
async def test_admin_dashboard_requires_claim() -> None:
    store = MemoryMultiUserStore()
    user = principal("uid-a")
    await provision_user(store, user)
    with pytest.raises(HTTPException) as denied:
        await build_admin_dashboard(store, user)
    assert denied.value.status_code == 403
    admin = AuthenticatedPrincipal(
        uid="uid-admin",
        email="admin@example.test",
        email_verified=True,
        admin=True,
    )
    dashboard = await build_admin_dashboard(store, admin)
    assert dashboard["access"] == "EXPLICIT_ADMIN_CLAIM"
    assert "conversation_messages" not in dashboard
    assert "memories" not in dashboard


@pytest.mark.asyncio
async def test_v1_onboarding_joins_default_community_and_scopes_bootstrap() -> None:
    store = MemoryMultiUserStore()
    user = principal("uid-community")
    await provision_user(store, user)
    await complete_onboarding(store, user, onboarding("Community Member"))
    memberships = list(store.collections["community_memberships"].values())
    assert len(memberships) == 1
    assert memberships[0]["community_id"] == DEFAULT_COMMUNITY_ID
    assert memberships[0]["status"] == "ACTIVE"
    task = await create_user_task(store, user, task_input("V1 community task"))
    assert task["community_id"] == DEFAULT_COMMUNITY_ID
    assert task["task_type"] == "ROOM_SHARE"
    bootstrap = await build_user_bootstrap(store, user)
    assert bootstrap["communities"][0]["community_id"] == DEFAULT_COMMUNITY_ID
    assert bootstrap["communityMemberships"][0]["role"] == "MEMBER"


@pytest.mark.asyncio
async def test_public_post_rejects_contact_and_precise_private_details() -> None:
    store = MemoryMultiUserStore()
    user = principal("uid-private")
    await provision_user(store, user)
    await complete_onboarding(store, user, onboarding("Private Member"))
    task = await create_user_task(store, user, task_input("Private-safe task"))
    with pytest.raises(ValueError):
        await publish_user_post(
            store,
            user,
            task_id=str(task["task_id"]),
            public_title="Contact me at private@example.test",
            public_summary="My hotel room number is 1204.",
            public_requirements=[],
        )
    assert store.collections["intent_posts"] == {}


@pytest.mark.asyncio
async def test_public_post_description_is_optional_and_falls_back_to_title() -> None:
    store = MemoryMultiUserStore()
    user = principal("uid-optional-summary")
    await provision_user(store, user)
    await complete_onboarding(store, user, onboarding("Optional Summary"))
    task = await create_user_task(store, user, task_input("Simple public title"))
    post = await publish_user_post(
        store,
        user,
        task_id=str(task["task_id"]),
        public_title="Simple public title",
        public_summary="",
        public_requirements=[],
    )
    assert post["public_summary"] == "Simple public title"


@pytest.mark.asyncio
async def test_closing_post_closes_request_and_releases_active_task_quota() -> None:
    store = MemoryMultiUserStore()
    user = principal("uid-close-request")
    await provision_user(store, user)
    await complete_onboarding(store, user, onboarding("Request Owner"))
    tasks = [
        await create_user_task(store, user, task_input(f"Active task {index}"))
        for index in range(3)
    ]
    post = await publish_user_post(
        store,
        user,
        task_id=str(tasks[0]["task_id"]),
        public_title="Request that can be closed",
        public_summary="Verify closing releases the user's active request slot.",
        public_requirements=[],
    )
    pending_decision_id = "decision-close-pending"
    await store.create(
        "decisions",
        pending_decision_id,
        {
            "decision_id": pending_decision_id,
            "owner_uid": user.uid,
            "task_id": tasks[0]["task_id"],
            "status": "OPEN",
        },
    )
    assessment_id = "assessment-close-pending"
    await store.create(
        "candidate_assessments",
        assessment_id,
        {
            "assessment_id": assessment_id,
            "owner_uid": user.uid,
            "task_id": tasks[0]["task_id"],
            "state": "CONTACTING",
        },
    )

    closed = await set_user_post_status(
        store,
        user,
        intent_id=str(post["intent_id"]),
        status="CLOSED",
    )

    assert closed["status"] == "CLOSED"
    stored_task = store.collections["task_workspaces"][str(tasks[0]["task_id"])]
    assert stored_task["status"] == "CANCELLED"
    assert store.collections["decisions"][pending_decision_id]["status"] == "CANCELLED"
    assert (
        store.collections["candidate_assessments"][assessment_id]["state"]
        == "WITHDRAWN"
    )
    replacement = await create_user_task(
        store, user, task_input("Replacement active task")
    )
    assert replacement["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_candidate_pool_reranks_multiple_candidates() -> None:
    store = MemoryMultiUserStore()
    users = [principal("uid-a"), principal("uid-b"), principal("uid-c")]
    tasks: list[dict[str, Any]] = []
    for user, name, end_day in zip(
        users, ("Alex", "Blair", "Casey"), (10, 7, 10), strict=True
    ):
        await provision_user(store, user)
        await complete_onboarding(store, user, onboarding(name))
        task = await create_user_task(
            store,
            user,
            task_input(f"{name} terms").model_copy(
                update={"date_end": date(2026, 7, end_day)}
            ),
        )
        await publish_user_post(
            store,
            user,
            task_id=str(task["task_id"]),
            public_title=f"{name} post",
            public_summary=f"{name} reports compatible ICML room-share dates.",
            public_requirements=["Quiet nights"],
        )
        tasks.append(task)
    posts = [await store.get("intent_posts", str(task["intent_id"])) for task in tasks]
    assert all(post is not None for post in posts)
    source = posts[0]
    assert source is not None
    for index, target in enumerate(posts[1:], start=1):
        assert target is not None
        await record_candidate_exchange(
            store,
            source_post=source,
            target_post=target,
            agent_messages={
                str(source["owner_agent_id"]): f"Source reversible turn {index}",
                str(target["owner_agent_id"]): f"Candidate reversible turn {index}",
            },
            invocation_id=f"invocation-{index}",
        )
    source_assessments = [
        item
        for item in store.collections["candidate_assessments"].values()
        if item.get("task_id") == tasks[0]["task_id"]
    ]
    assert len(source_assessments) == 2
    initial_order = sorted(source_assessments, key=lambda item: item["current_rank"])
    assert initial_order[0]["candidate_intent_id"] == tasks[2]["intent_id"]
    await set_candidate_state(
        store,
        owner_uid=users[0].uid,
        task_id=str(tasks[0]["task_id"]),
        candidate_intent_id=str(tasks[2]["intent_id"]),
        state="BACKUP",
    )
    reranked = sorted(
        [
            item
            for item in store.collections["candidate_assessments"].values()
            if item.get("task_id") == tasks[0]["task_id"]
        ],
        key=lambda item: item["current_rank"],
    )
    assert reranked[0]["candidate_intent_id"] == tasks[1]["intent_id"]
    assert len(store.collections["candidate_rank_events"]) >= 3
    assert len(store.collections["coordination_rooms"]) == 2
    closed_post = dict(store.collections["intent_posts"][str(tasks[1]["intent_id"])])
    closed_post["status"] = "CLOSED"
    await store.upsert("intent_posts", str(tasks[1]["intent_id"]), closed_post)
    changed = await reconcile_candidate_availability(
        store, now=datetime(2026, 9, 1, tzinfo=UTC)
    )
    assert changed >= 1
    source_closed = next(
        item
        for item in store.collections["candidate_assessments"].values()
        if item.get("task_id") == tasks[0]["task_id"]
        and item.get("candidate_intent_id") == tasks[1]["intent_id"]
    )
    assert source_closed["state"] == "CLOSED"


@pytest.mark.asyncio
async def test_only_confirmed_memory_enters_agent_runtime() -> None:
    store = MemoryMultiUserStore()
    user = principal("uid-memory")
    await provision_user(store, user)
    agent_id = agent_id_for_uid(user.uid)
    proposed = {
        "memory_id": "memory-proposed",
        "owner_uid": user.uid,
        "owner_agent_id": agent_id,
        "content": "Prefers quiet rooms.",
        "scope": "GLOBAL",
        "status": "PROPOSED",
        "confirmation_status": "PROPOSED",
    }
    confirmed = {
        **proposed,
        "memory_id": "memory-confirmed",
        "content": "Avoids smoking rooms.",
        "status": "CONFIRMED",
        "confirmation_status": "CONFIRMED",
    }
    await store.create("memories", "memory-proposed", proposed)
    await store.create("memories", "memory-confirmed", confirmed)
    runtime = await load_personal_agent(store, agent_id)
    assert [item["memory_id"] for item in runtime["permitted_memories"]] == [
        "memory-confirmed"
    ]
    assert memory_is_confirmed(proposed) is False
    updated = await update_memory_lifecycle(
        store, user, "memory-proposed", action="CONFIRM"
    )
    assert updated["status"] == "CONFIRMED"
    assert memory_is_confirmed(updated) is True
    with pytest.raises(PermissionError):
        await update_memory_lifecycle(
            store, principal("uid-other"), "memory-proposed", action="ARCHIVE"
        )


@pytest.mark.asyncio
async def test_two_users_receive_isolated_private_bootstraps_and_real_posts() -> None:
    store = MemoryMultiUserStore()
    user_a, user_b = principal("uid-a"), principal("uid-b")
    await provision_user(store, user_a)
    await provision_user(store, user_b)
    await complete_onboarding(store, user_a, onboarding("Alex"))
    await complete_onboarding(store, user_b, onboarding("Blair"))
    task_a = await create_user_task(store, user_a, task_input("Alex request"))
    task_b = await create_user_task(store, user_b, task_input("Blair request"))
    await publish_user_post(
        store,
        user_a,
        task_id=str(task_a["task_id"]),
        public_title="Alex public post",
        public_summary="Looking to share an ICML hotel room in Seoul.",
        public_requirements=["Adult ICML attendee"],
    )
    await publish_user_post(
        store,
        user_b,
        task_id=str(task_b["task_id"]),
        public_title="Blair public post",
        public_summary="Seeking a compatible ICML room share.",
        public_requirements=["Adult ICML attendee"],
    )

    bootstrap_a = await build_user_bootstrap(store, user_a)
    bootstrap_b = await build_user_bootstrap(store, user_b)
    assert {item["task_id"] for item in bootstrap_a["tasks"]} == {task_a["task_id"]}
    assert {item["task_id"] for item in bootstrap_b["tasks"]} == {task_b["task_id"]}
    assert bootstrap_a["myPosts"][0]["task_id"] == task_a["task_id"]
    assert bootstrap_b["myPosts"][0]["task_id"] == task_b["task_id"]
    assert bootstrap_a["explorePosts"][0]["public_title"] == "Blair public post"
    assert (
        bootstrap_a["explorePosts"][0]["public_summary"]
        == "Seeking a compatible ICML room share."
    )
    assert bootstrap_b["explorePosts"][0]["public_title"] == "Alex public post"
    assert "owner_uid" not in bootstrap_a["explorePosts"][0]
    assert "email" not in bootstrap_a["explorePosts"][0]
    assert "maximum_additional_cost_usd" not in bootstrap_a["explorePosts"][0]
    assert "task_id" not in bootstrap_a["explorePosts"][0]
    assert "Blair request: find" not in str(bootstrap_a)
    assert "Alex request: find" not in str(bootstrap_b)


def test_peer_agent_projection_contains_only_reviewed_public_fields() -> None:
    projected = public_agent_projection(
        {
            "intent_id": "intent-a",
            "owner_agent_id": "agent-a",
            "public_display_name": "Alex",
            "public_summary": "Public summary",
            "public_constraints": {"event": "ICML"},
            "owner_uid": "private-uid",
            "task_id": "private-task-id",
            "email": "private@example.test",
            "raw_user_goal": "private goal",
            "_updateTime": "internal-version",
        }
    )
    assert projected["public_summary"] == "Public summary"
    assert "owner_uid" not in projected
    assert "task_id" not in projected
    assert "email" not in projected
    assert "raw_user_goal" not in projected
    assert "_updateTime" not in projected


@pytest.mark.asyncio
async def test_daily_agent_turn_quota_is_charged_atomically() -> None:
    store = MemoryMultiUserStore()
    await provision_user(store, principal("uid-a"))
    await provision_user(store, principal("uid-b"))
    timestamp = datetime(2026, 8, 29, tzinfo=UTC)
    await consume_daily_agent_turns(store, ["uid-a", "uid-b"], now=timestamp)
    assert store.collections["usage_quotas"]["uid-a"]["agent_turns_today"] == 1
    assert store.collections["usage_quotas"]["uid-b"]["agent_turns_today"] == 1
    exhausted = dict(store.collections["usage_quotas"]["uid-a"])
    exhausted["agent_turns_today"] = exhausted["daily_agent_turn_limit"]
    exhausted["quota_date"] = timestamp.date().isoformat()
    await store.upsert("usage_quotas", "uid-a", exhausted)
    with pytest.raises(AgentRuntimeError, match="daily Agent turn quota"):
        await consume_daily_agent_turns(store, ["uid-a", "uid-b"], now=timestamp)
    assert store.collections["usage_quotas"]["uid-b"]["agent_turns_today"] == 1


@pytest.mark.asyncio
async def test_unverified_user_cannot_publish() -> None:
    store = MemoryMultiUserStore()
    user = principal("uid-unverified", verified=False)
    await provision_user(store, user)
    await complete_onboarding(store, user, onboarding("Unverified"))
    task = await create_user_task(store, user, task_input("Private draft"))
    with pytest.raises(HTTPException) as error:
        await publish_user_post(
            store,
            user,
            task_id=str(task["task_id"]),
            public_title="Must not publish",
            public_summary="This should remain a private draft only.",
            public_requirements=[],
        )
    assert error.value.status_code == 403
    assert store.collections["intent_posts"] == {}


@pytest.mark.asyncio
async def test_user_cannot_publish_another_users_task() -> None:
    store = MemoryMultiUserStore()
    user_a, user_b = principal("uid-a"), principal("uid-b")
    for user, name in ((user_a, "Alex"), (user_b, "Blair")):
        await provision_user(store, user)
        await complete_onboarding(store, user, onboarding(name))
    task_a = await create_user_task(store, user_a, task_input("Alex private task"))
    with pytest.raises(HTTPException) as error:
        await publish_user_post(
            store,
            user_b,
            task_id=str(task_a["task_id"]),
            public_title="Impersonated post",
            public_summary="User B must not publish this.",
            public_requirements=[],
        )
    assert error.value.status_code == 403


def test_protected_app_routes_use_token_uid_and_reject_idor(monkeypatch) -> None:
    store = MemoryMultiUserStore()
    monkeypatch.setattr(web, "_store", lambda: store)
    web.app.state.auth_token_verifier = ApiVerifier()
    client = TestClient(web.app)
    headers_a = {"Authorization": "Bearer user-a"}
    headers_b = {"Authorization": "Bearer user-b"}

    assert client.get("/api/app/bootstrap").status_code == 401
    assert client.post("/api/app/provision", headers=headers_a).status_code == 200
    assert client.post("/api/app/provision", headers=headers_b).status_code == 200
    for headers, name in ((headers_a, "Alex"), (headers_b, "Blair")):
        response = client.put(
            "/api/app/onboarding",
            headers=headers,
            json={
                "display_name": name,
                "timezone": "Asia/Shanghai",
                "general_location": "Shanghai",
                "language": "English",
                "adult_confirmed": True,
                "public_profile_visible": True,
                "default_autonomy_mode": "COPILOT",
                "public_sharing_policy": "Reviewed post fields only.",
                "agent_sharing_policy": "Minimum task evidence.",
                "always_ask_policy": "Ask before commitment.",
            },
        )
        assert response.status_code == 200

    created = client.post(
        "/api/app/tasks",
        headers=headers_a,
        json={
            "title": "Alex ICML request",
            "task_type": "conference_room_share",
            "goal": "Find an adult ICML attendee for a quiet hotel room share.",
            "event": "ICML",
            "location": "Seoul",
            "date_start": "2026-07-06",
            "date_end": "2026-07-10",
            "public_requirements": ["Adult ICML attendee"],
            "maximum_additional_cost_usd": 70,
            "partial_date_overlap_allowed": True,
        },
    )
    assert created.status_code == 200
    task_id = created.json()["task"]["task_id"]
    owner_view = client.get(f"/api/app/tasks/{task_id}", headers=headers_a)
    attacker_view = client.get(f"/api/app/tasks/{task_id}", headers=headers_b)
    assert owner_view.status_code == 200
    assert attacker_view.status_code == 403
    assert "quiet hotel" not in attacker_view.text

    impersonation = client.post(
        "/api/app/tasks",
        headers=headers_b,
        json={
            "owner_uid": "uid-a",
            "title": "Impersonation",
            "task_type": "conference_room_share",
            "goal": "Attempt to create a task while claiming another owner UID.",
            "event": "ICML",
            "location": "Seoul",
            "date_start": "2026-07-06",
            "date_end": "2026-07-10",
            "public_requirements": [],
            "maximum_additional_cost_usd": 70,
            "partial_date_overlap_allowed": True,
        },
    )
    assert impersonation.status_code == 422


@pytest.mark.asyncio
async def test_two_agents_two_humans_commit_one_match_and_shared_room() -> None:
    store = MemoryMultiUserStore()
    user_a, user_b, attacker = (
        principal("uid-a"),
        principal("uid-b"),
        principal("uid-attacker"),
    )
    for user, name in (
        (user_a, "Alex"),
        (user_b, "Blair"),
        (attacker, "Attacker"),
    ):
        await provision_user(store, user)
        await complete_onboarding(store, user, onboarding(name))
    task_a = await create_user_task(store, user_a, task_input("Alex live post"))
    task_b = await create_user_task(store, user_b, task_input("Blair live post"))
    for user, task, title in (
        (user_a, task_a, "Alex public post"),
        (user_b, task_b, "Blair public post"),
    ):
        await publish_user_post(
            store,
            user,
            task_id=str(task["task_id"]),
            public_title=title,
            public_summary="Compatible adult ICML hotel room share in Seoul.",
            public_requirements=["Adult ICML attendee"],
        )

    proposal = await process_published_intent(
        store, str(task_a["intent_id"]), agent_messages=_agent_messages_for_test()
    )
    proposal_id = str(proposal["proposal_id"])
    assert proposal["participant_agent_ids"] == [
        agent_id_for_uid("uid-a"),
        agent_id_for_uid("uid-b"),
    ]
    assert len(store.collections["proposal_acceptances"]) == 2
    assert len(store.collections["decisions"]) == 4
    assert len(store.collections["room_participants"]) == 2
    assert {
        item["contact_count"] for item in store.collections["task_workspaces"].values()
    } == {1}

    with pytest.raises(PermissionError):
        await approve_multi_user_proposal(
            store,
            attacker,
            proposal_id=proposal_id,
            proposal_version=1,
            confirmation="APPROVE VERSION 1",
        )
    first = await approve_multi_user_proposal(
        store,
        user_a,
        proposal_id=proposal_id,
        proposal_version=1,
        confirmation="APPROVE VERSION 1",
    )
    assert first["status"] == "WAITING_FOR_OTHER_HUMAN"
    assert store.collections["matches"] == {}

    second = await approve_multi_user_proposal(
        store,
        user_b,
        proposal_id=proposal_id,
        proposal_version=1,
        confirmation="APPROVE VERSION 1",
    )
    assert second["status"] == "MATCH_COMMITTED"
    assert len(store.collections["matches"]) == 1
    assert {item["status"] for item in store.collections["intent_posts"].values()} == {
        "MATCHED"
    }
    room = next(iter(store.collections["coordination_rooms"].values()))
    assert room["room_type"] == "SHARED_COORDINATION_ROOM"
    assert room["human_participation_available"] is True
    assert len(store.collections["relationships"]) == 2
    offered = await offer_contact_card(
        store,
        user_a,
        match_id=proposal_id,
        body=ContactCardInput(public_email="alex-public@example.test"),
    )
    assert offered["fields"] == {"public_email": "alex-public@example.test"}
    visible_to_peer = await list_match_contact_cards(
        store, user_b, match_id=proposal_id
    )
    assert visible_to_peer[0]["fields"] == offered["fields"]
    await revoke_contact_card(store, user_a, match_id=proposal_id)
    assert await list_match_contact_cards(store, user_b, match_id=proposal_id) == []
    outcome = await submit_outcome_check_in(
        store,
        user_a,
        match_id=proposal_id,
        body=OutcomeCheckInInput(
            did_plan_happen=True,
            would_coordinate_again=True,
            agreed_term_inaccurate=False,
            optional_feedback="Private owner feedback.",
        ),
    )
    assert outcome["did_plan_happen"] is True
    assert len(store.collections["relationship_events"]) == 3

    bootstrap_a = await build_user_bootstrap(store, user_a)
    bootstrap_b = await build_user_bootstrap(store, user_b)
    assert len(bootstrap_a["matches"]) == 1
    assert len(bootstrap_b["matches"]) == 1
    assert len(bootstrap_a["rooms"]) == 1
    assert len(bootstrap_b["rooms"]) == 1
    assert "participant_uids" not in bootstrap_a["rooms"][0]
    duplicate = await approve_multi_user_proposal(
        store,
        user_a,
        proposal_id=proposal_id,
        proposal_version=1,
        confirmation="APPROVE VERSION 1",
    )
    assert duplicate["status"] == "MATCH_COMMITTED"
    assert len(store.collections["matches"]) == 1

    second_task_a = await create_user_task(
        store, user_a, task_input("Alex second live post")
    )
    second_task_b = await create_user_task(
        store, user_b, task_input("Blair second live post")
    )
    for user, task, title in (
        (user_a, second_task_a, "Alex second public post"),
        (user_b, second_task_b, "Blair second public post"),
    ):
        await publish_user_post(
            store,
            user,
            task_id=str(task["task_id"]),
            public_title=title,
            public_summary="A second compatible ICML room share.",
            public_requirements=["Adult ICML attendee"],
        )
    second_proposal = await process_published_intent(
        store,
        str(second_task_a["intent_id"]),
        agent_messages=_agent_messages_for_test(),
    )
    second_proposal_id = str(second_proposal["proposal_id"])
    for user in (user_a, user_b):
        result = await approve_multi_user_proposal(
            store,
            user,
            proposal_id=second_proposal_id,
            proposal_version=1,
            confirmation="APPROVE VERSION 1",
        )
    assert result["status"] == "MATCH_COMMITTED"
    assert len(store.collections["matches"]) == 2
    assert len(store.collections["relationships"]) == 2
    assert {
        item["plans_committed"] for item in store.collections["relationships"].values()
    } == {2}
    assert {
        item["successful_plans"] for item in store.collections["relationships"].values()
    } == {0, 1}


@pytest.mark.asyncio
async def test_firestore_adk_session_service_persists_owner_scoped_session() -> None:
    store = MemoryMultiUserStore()
    first = FirestoreSessionService(store)
    created = await first.create_session(
        app_name="pairpilot_real_personal_agent",
        user_id="uid-a",
        session_id="session-a",
        state={"conversation_id": "user:uid-a:global"},
    )
    second = FirestoreSessionService(store)
    loaded = await second.get_session(
        app_name="pairpilot_real_personal_agent",
        user_id="uid-a",
        session_id="session-a",
    )
    cross_user = await second.get_session(
        app_name="pairpilot_real_personal_agent",
        user_id="uid-b",
        session_id="session-a",
    )
    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.state["conversation_id"] == "user:uid-a:global"
    assert cross_user is None


def test_real_personal_agent_stream_is_authenticated_idempotent_and_replayable(
    monkeypatch,
) -> None:
    store = MemoryMultiUserStore()
    calls = 0

    async def fake_turn(
        runtime_store,
        runtime_principal,
        *,
        conversation,
        content,
        client_message_id,
        invocation_id,
    ):
        nonlocal calls
        calls += 1
        assert runtime_store is store
        assert runtime_principal.uid == "uid-a"
        assert conversation["conversation_id"] == "user:uid-a:global"
        assert content == "Help me find an ICML roommate."
        yield {
            "type": "message.accepted",
            "invocation_id": invocation_id,
            "client_message_id": client_message_id,
        }
        yield {
            "type": "agent.started",
            "invocation_id": invocation_id,
            "model_id": "test-live-model",
            "execution_mode": "LIVE",
        }
        yield {
            "type": "agent.text.delta",
            "invocation_id": invocation_id,
            "delta": "What dates should I use?",
        }
        yield {
            "type": "agent.completed",
            "invocation_id": invocation_id,
            "assistant_message_id": "assistant-a",
            "message": {"content": "What dates should I use?"},
        }

    monkeypatch.setattr(web, "_store", lambda: store)
    monkeypatch.setattr(
        web.app.state, "auth_token_verifier", ApiVerifier(), raising=False
    )
    monkeypatch.setattr(
        web.app.state, "personal_agent_turn_runner", fake_turn, raising=False
    )
    client = TestClient(web.app)
    headers_a = {"Authorization": "Bearer user-a"}
    headers_b = {"Authorization": "Bearer user-b"}
    assert client.post("/api/app/provision", headers=headers_a).status_code == 200
    assert client.post("/api/app/provision", headers=headers_b).status_code == 200
    body = {
        "content": "Help me find an ICML roommate.",
        "client_message_id": "client-message-0001",
        "task_id": None,
    }
    first = client.post(
        "/api/v1/conversations/user:uid-a:global/messages",
        headers=headers_a,
        json=body,
    )
    replay = client.post(
        "/api/v1/conversations/user:uid-a:global/messages",
        headers=headers_a,
        json=body,
    )
    denied = client.post(
        "/api/v1/conversations/user:uid-a:global/messages",
        headers=headers_b,
        json={**body, "client_message_id": "client-message-0002"},
    )
    assert first.status_code == 200
    assert "event: agent.text.delta" in first.text
    assert "event: agent.completed" in first.text
    assert replay.status_code == 200
    assert replay.text == first.text
    assert denied.status_code == 403
    assert calls == 1
    user_messages = [
        item
        for item in store.collections["conversation_messages"].values()
        if item.get("role") == "USER"
        and item.get("client_message_id") == "client-message-0001"
    ]
    assert len(user_messages) == 1


def test_model_failure_stream_is_honest_and_saves_no_assistant(monkeypatch) -> None:
    store = MemoryMultiUserStore()

    async def failing_turn(
        _store,
        _principal,
        *,
        conversation,
        content,
        client_message_id,
        invocation_id,
    ):
        del conversation, content, client_message_id
        yield {
            "type": "message.accepted",
            "invocation_id": invocation_id,
        }
        raise RuntimeError("simulated Vertex failure")

    monkeypatch.setattr(web, "_store", lambda: store)
    monkeypatch.setattr(
        web.app.state, "auth_token_verifier", ApiVerifier(), raising=False
    )
    monkeypatch.setattr(
        web.app.state, "personal_agent_turn_runner", failing_turn, raising=False
    )
    client = TestClient(web.app)
    headers = {"Authorization": "Bearer user-a"}
    assert client.post("/api/app/provision", headers=headers).status_code == 200
    response = client.post(
        "/api/v1/conversations/user:uid-a:global/messages",
        headers=headers,
        json={
            "content": "This turn should fail honestly.",
            "client_message_id": "failure-message-0001",
        },
    )
    assert response.status_code == 200
    assert "event: agent.error" in response.text
    assert "simulated Vertex failure" not in response.text
    assert not any(
        item.get("role") == "PERSONAL_AGENT"
        for item in store.collections["conversation_messages"].values()
    )


def test_global_conversation_can_focus_an_owned_task_without_switching_threads(
    monkeypatch,
) -> None:
    store = MemoryMultiUserStore()
    observed_task_ids: list[str | None] = []

    async def focused_turn(
        _store,
        _principal,
        *,
        conversation,
        content,
        client_message_id,
        invocation_id,
    ):
        del content, client_message_id
        observed_task_ids.append(conversation.get("task_id"))
        yield {"type": "message.accepted", "invocation_id": invocation_id}
        yield {
            "type": "agent.completed",
            "invocation_id": invocation_id,
            "assistant_message_id": "assistant-focused",
            "message": {"content": "I kept the same chat and focused the task."},
        }

    monkeypatch.setattr(web, "_store", lambda: store)
    monkeypatch.setattr(
        web.app.state, "auth_token_verifier", ApiVerifier(), raising=False
    )
    monkeypatch.setattr(
        web.app.state, "personal_agent_turn_runner", focused_turn, raising=False
    )
    client = TestClient(web.app)
    headers = {"Authorization": "Bearer user-a"}
    assert client.post("/api/app/provision", headers=headers).status_code == 200
    assert (
        client.put(
            "/api/app/onboarding",
            headers=headers,
            json=onboarding("Alex").model_dump(mode="json"),
        ).status_code
        == 200
    )
    task_response = client.post(
        "/api/app/tasks",
        headers=headers,
        json=task_input("Disney buddy").model_dump(mode="json"),
    )
    task_id = task_response.json()["task"]["task_id"]
    response = client.post(
        "/api/v1/conversations/user:uid-a:global/messages",
        headers=headers,
        json={
            "content": "Please revise this post.",
            "client_message_id": "focused-message-0001",
            "task_id": task_id,
        },
    )
    assert response.status_code == 200
    assert observed_task_ids == [task_id]
    assert (
        store.collections["conversations"]["user:uid-a:global"].get("task_id") is None
    )


def test_global_conversation_accepts_explicit_null_task_id_on_followup(
    monkeypatch,
) -> None:
    store = MemoryMultiUserStore()
    observed_task_ids: list[str | None] = []

    async def successful_turn(
        _store,
        _principal,
        *,
        conversation,
        content,
        client_message_id,
        invocation_id,
    ):
        del _store, _principal, content, client_message_id
        observed_task_ids.append(conversation.get("task_id"))
        yield {"type": "message.accepted", "invocation_id": invocation_id}
        yield {
            "type": "agent.completed",
            "invocation_id": invocation_id,
            "assistant_message_id": f"assistant-{len(observed_task_ids)}",
            "message": {"content": "The global conversation is still available."},
        }

    monkeypatch.setattr(web, "_store", lambda: store)
    monkeypatch.setattr(
        web.app.state, "auth_token_verifier", ApiVerifier(), raising=False
    )
    monkeypatch.setattr(
        web.app.state, "personal_agent_turn_runner", successful_turn, raising=False
    )
    client = TestClient(web.app)
    headers = {"Authorization": "Bearer user-a"}
    assert client.post("/api/app/provision", headers=headers).status_code == 200
    conversation = store.collections["conversations"]["user:uid-a:global"]
    conversation["task_id"] = None

    for index in (1, 2):
        response = client.post(
            "/api/v1/conversations/user:uid-a:global/messages",
            headers=headers,
            json={
                "content": f"Global follow-up {index}",
                "client_message_id": f"global-null-followup-{index}",
            },
        )
        assert response.status_code == 200
        assert "event: agent.completed" in response.text
        assert "Task was not found" not in response.text

    assert observed_task_ids == [None, None]


@pytest.mark.asyncio
async def test_material_proposal_version_change_invalidates_old_approvals() -> None:
    store = MemoryMultiUserStore()
    user_a, user_b = principal("uid-a"), principal("uid-b")
    for user, name in ((user_a, "Alex"), (user_b, "Blair")):
        await provision_user(store, user)
        await complete_onboarding(store, user, onboarding(name))
    task_a = await create_user_task(store, user_a, task_input("Alex terms"))
    task_b = await create_user_task(store, user_b, task_input("Blair terms"))
    for user, task, title in (
        (user_a, task_a, "Alex post"),
        (user_b, task_b, "Blair post"),
    ):
        await publish_user_post(
            store,
            user,
            task_id=str(task["task_id"]),
            public_title=title,
            public_summary="Compatible ICML room share.",
            public_requirements=[],
        )
    proposal = await process_published_intent(
        store, str(task_a["intent_id"]), agent_messages=_agent_messages_for_test()
    )
    proposal_id = str(proposal["proposal_id"])
    await approve_multi_user_proposal(
        store,
        user_a,
        proposal_id=proposal_id,
        proposal_version=1,
        confirmation="APPROVE VERSION 1",
    )
    changed = dict(store.collections["proposals"][proposal_id])
    changed["version"] = 2
    changed["terms"] = {**dict(changed["terms"]), "cost_difference_usd": 25}
    await store.upsert("proposals", proposal_id, changed)
    with pytest.raises(MultiUserCommitError):
        await commit_dual_approved_match(store, proposal_id=proposal_id)
    assert store.collections["matches"] == {}
