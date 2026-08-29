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
from pairpilot_orchestrator.infrastructure.google_cloud import decode_fields
from pairpilot_orchestrator.multi_user_platform import (
    agent_id_for_uid,
    build_user_bootstrap,
    complete_onboarding,
    create_user_task,
    provision_user,
    publish_user_post,
)
from pairpilot_schemas import (
    CreateUserTaskInput,
    OnboardingInput,
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

    async def get(
        self, collection: str, document_id: str
    ) -> dict[str, Any] | None:
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
                current is None
                or current.get("_updateTime") != condition["updateTime"]
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
    assert {item["task_id"] for item in bootstrap_a["tasks"]} == {
        task_a["task_id"]
    }
    assert {item["task_id"] for item in bootstrap_b["tasks"]} == {
        task_b["task_id"]
    }
    assert bootstrap_a["explorePosts"][0]["public_title"] == "Blair public post"
    assert bootstrap_b["explorePosts"][0]["public_title"] == "Alex public post"
    assert "owner_uid" not in bootstrap_a["explorePosts"][0]
    assert "email" not in bootstrap_a["explorePosts"][0]
    assert "maximum_additional_cost_usd" not in bootstrap_a["explorePosts"][0]
    assert "Blair request: find" not in str(bootstrap_a)
    assert "Alex request: find" not in str(bootstrap_b)


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
