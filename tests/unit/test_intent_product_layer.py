import importlib.util
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pairpilot_orchestrator import web
from pairpilot_orchestrator.domain import AuthorityError, CoordinationAuthority
from pairpilot_orchestrator.workflow import GoldenPathRuntime
from pairpilot_schemas import (
    AgentOnlyDraft,
    FieldSource,
    IntentDraft,
    Proposal,
    canonical_intent_pair,
)

NOW = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)


def load_seed_module() -> Any:
    path = Path(__file__).parents[2] / "infra" / "seed_demo.py"
    spec = importlib.util.spec_from_file_location("seed_demo_intent", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MemoryStore:
    def __init__(self, collections: dict[str, dict[str, dict[str, Any]]]) -> None:
        self.collections = collections
        self.events: dict[str, dict[str, Any]] = {}
        self.turns: list[dict[str, Any]] = []

    async def get(self, collection: str, document_id: str) -> dict[str, Any] | None:
        value = self.collections.get(collection, {}).get(document_id)
        return dict(value) if value is not None else None

    async def list_documents(self, collection: str) -> list[dict[str, Any]]:
        return [
            {**value, "_id": document_id}
            for document_id, value in self.collections.get(collection, {}).items()
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
        return dict(data)

    async def write_event(self, **event: Any) -> dict[str, Any]:
        key = str(event["idempotency_key"])
        created = key not in self.events
        self.events.setdefault(key, dict(event))
        return {"event_id": key, "created": created, "published": True}

    async def write_agent_turn(self, **turn: Any) -> str:
        self.turns.append(turn)
        return "turn-1"


def test_reset_seed_has_peer_posts_but_no_qi_request() -> None:
    data = load_seed_module().documents()
    intents = data["intents"]
    assert set(intents) == {
        "intent_maya_icml_roommate",
        "intent_lena_icml_roommate",
        "intent_nora_icml_dinner",
        "intent_min_icml_workshop",
        "intent_sam_seoul_explore",
        "intent_zoe_hackathon_teammate",
    }
    assert all(item["status"] == "OPEN" for item in intents.values())
    assert all(item["owner_agent_id"] != "qi-agent" for item in intents.values())
    assert "overnightRoutineClaim" not in data["agent_public_cards"]["maya-agent"]
    assert "pricePreference" not in data["agent_public_cards"]["lena-agent"]
    assert "alice-agent__maya-agent__conference-coordination" in data["relationships"]


@pytest.mark.asyncio
async def test_search_open_intents_returns_only_public_open_posts() -> None:
    store = MemoryStore(
        {
            "intents": {
                "intent_maya": {
                    "intent_id": "intent_maya",
                    "owner_agent_id": "maya-agent",
                    "intent_type": "conference_room_share",
                    "public_title": "Maya request",
                    "public_summary": "Share in Seoul",
                    "public_constraints": {
                        "event": "ICML",
                        "location": "Seoul",
                        "date_start": "2026-07-07",
                        "date_end": "2026-07-10",
                    },
                    "public_requirements": [],
                    "capacity_remaining": 1,
                    "status": "OPEN",
                    "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                },
                "intent_lena": {
                    "intent_id": "intent_lena",
                    "owner_agent_id": "lena-agent",
                    "intent_type": "conference_room_share",
                    "public_title": "Closed request",
                    "public_summary": "No longer searchable",
                    "public_constraints": {
                        "event": "ICML",
                        "location": "Seoul",
                        "date_start": "2026-07-06",
                        "date_end": "2026-07-10",
                    },
                    "agent_only_constraints": {"must_not_leak": True},
                    "capacity_remaining": 0,
                    "status": "MATCHED",
                    "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                },
            }
        }
    )
    runtime = GoldenPathRuntime(
        store=store,  # type: ignore[arg-type]
        peer_base_url="https://peer.example",
        model_id="gemini-3.7-flash",
        source_intent_id="intent_qi",
    )
    runtime.goal_start = date(2026, 7, 6)
    runtime.goal_end = date(2026, 7, 10)
    result = await runtime.search_open_intents(
        "roommate",  # type: ignore[arg-type]  # common live-model synonym
        "Seoul",
    )
    assert [item["intent_id"] for item in result["open_intents"]] == ["intent_maya"]
    assert "agent_only_constraints" not in str(result)
    assert runtime.discovered_intents == {"intent_maya": "maya-agent"}


def proposal(
    *, source: str, target: str, candidate: str, maximum: int = 70
) -> Proposal:
    return Proposal(
        source_intent_id=source,
        target_intent_id=target,
        pair_session_id=canonical_intent_pair(source, target),
        candidate_agent_id=candidate,
        version=1,
        shared_start=date(2026, 7, 7),
        shared_end=date(2026, 7, 10),
        solo_dates=[date(2026, 7, 6)],
        additional_cost_usd=62,
        delegated_maximum_usd=maximum,
        terms=["equal split"],
        disclosure_hash="a" * 64,
        expires_at=NOW + timedelta(minutes=30),
    )


def test_user_cost_boundary_changes_authority() -> None:
    authority = CoordinationAuthority()
    authority.add_proposal(
        proposal(
            source="intent_qi_70",
            target="intent_maya_70",
            candidate="maya-agent",
            maximum=70,
        )
    )
    with pytest.raises(AuthorityError, match="exceeds delegated cost authority"):
        CoordinationAuthority().add_proposal(
            proposal(
                source="intent_qi_50",
                target="intent_maya_50",
                candidate="maya-agent",
                maximum=50,
            )
        )


def test_hold_reserves_intent_capacity_not_entire_agent() -> None:
    authority = CoordinationAuthority()
    roommate = proposal(
        source="intent_qi_roommate",
        target="intent_maya_roommate",
        candidate="maya-agent",
    )
    dinner = proposal(
        source="intent_qi_dinner",
        target="intent_maya_dinner",
        candidate="maya-agent",
    )
    authority.add_proposal(roommate)
    authority.add_proposal(dinner)
    hold_expiry = datetime.now(UTC) + timedelta(minutes=15)
    authority.place_hold(roommate.proposal_id, expires_at=hold_expiry)
    authority.place_hold(dinner.proposal_id, expires_at=hold_expiry)
    assert len(authority.holds) == 2


def test_proposal_versions_and_conflicts_are_intent_scoped() -> None:
    authority = CoordinationAuthority()
    first = proposal(
        source="intent_qi_roommate",
        target="intent_maya_roommate",
        candidate="maya-agent",
    )
    distinct_pair = proposal(
        source="intent_qi_dinner",
        target="intent_maya_dinner",
        candidate="maya-agent",
    )
    authority.add_proposal(first)
    authority.add_proposal(distinct_pair)
    assert first.version == distinct_pair.version == 1

    crossed = proposal(
        source="intent_other",
        target="intent_qi_roommate",
        candidate="lena-agent",
    )
    authority.add_proposal(crossed)
    hold_expiry = datetime.now(UTC) + timedelta(minutes=15)
    authority.place_hold(first.proposal_id, expires_at=hold_expiry)
    with pytest.raises(AuthorityError, match="conflicting active hold"):
        authority.place_hold(crossed.proposal_id, expires_at=hold_expiry)


def draft_fixture(maximum: int = 70) -> IntentDraft:
    provenance = {
        field: FieldSource.EXPLICIT_USER_INPUT
        for field in {
            "intent_type",
            "public_title",
            "public_summary",
            "event",
            "location",
            "date_start",
            "date_end",
            "roommate_gender_preference",
            "maximum_additional_cost_usd",
            "partial_date_overlap_allowed",
            "quiet_overnight_compatibility",
        }
    }
    return IntentDraft(
        intent_type="conference_room_share",
        public_title="Looking for an ICML hotel roommate",
        public_summary=(
            "Looking for a female ICML attendee to share a hotel room in Seoul "
            "from July 6 to July 10."
        ),
        event="ICML",
        location="Seoul",
        date_start=date(2026, 7, 6),
        date_end=date(2026, 7, 10),
        roommate_gender_preference="female",
        public_requirements=["equal cost split preferred"],
        agent_only=AgentOnlyDraft(
            quiet_overnight_compatibility_importance="high",
            partial_date_overlap_allowed=True,
            maximum_additional_cost_usd=maximum,
        ),
        field_provenance=provenance,
        uncertainties=[],
    )


def test_draft_publish_and_public_projection(monkeypatch) -> None:
    store = MemoryStore({})

    async def fake_draft(raw_goal: str) -> IntentDraft:
        assert "$70" in raw_goal
        return draft_fixture()

    monkeypatch.setattr(web, "_store", lambda: store)
    monkeypatch.setattr(web, "draft_with_qi_agent", fake_draft)
    client = TestClient(web.app)
    raw_goal = (
        "Find me a female roommate for ICML in Seoul from July 6 to July 10. "
        "Quiet matters and partial overlap is okay below $70."
    )
    drafted = client.post("/api/intents/draft", json={"raw_goal": raw_goal})
    assert drafted.status_code == 200
    intent_id = drafted.json()["publicPost"]["intent_id"]
    assert store.collections["intents"][intent_id]["status"] == "DRAFT"
    assert "light sleeper" not in str(store.collections["intents"][intent_id]).lower()
    payload = {
        "intent_id": intent_id,
        "public_title": "Looking for an ICML hotel roommate",
        "public_summary": "Female ICML attendee seeking a Seoul room share.",
        "event": "ICML",
        "location": "Seoul",
        "date_start": "2026-07-06",
        "date_end": "2026-07-10",
        "roommate_gender_preference": "female",
        "public_requirements": ["equal split preferred"],
        "quiet_overnight_compatibility_importance": "high",
        "maximum_additional_cost_usd": 70,
        "partial_date_overlap_allowed": True,
    }
    published = client.post("/api/intents/publish", json=payload)
    duplicate = client.post("/api/intents/publish", json=payload)
    assert published.status_code == duplicate.status_code == 200
    assert store.collections["intents"][intent_id]["status"] == "OPEN"
    provenance = store.collections["intents"][intent_id]["field_provenance"]
    assert provenance["maximum_additional_cost_usd"] == "explicit_user_input"
    assert provenance["public_summary"] == "user_edit"
    assert duplicate.json()["created"] is False
    public = client.get(f"/api/intents/{intent_id}").json()
    assert "raw_user_goal_ref" not in public
    assert "agent_only_constraints" not in public
    published_events = [
        item
        for item in store.events.values()
        if item["event_type"] == "intent.published"
    ]
    assert len(published_events) == 1


def test_multiple_active_qi_drafts_are_allowed_for_isolated_tasks(monkeypatch) -> None:
    store = MemoryStore(
        {
            "intents": {
                "intent_qi_existing": {
                    "intent_id": "intent_qi_existing",
                    "owner_agent_id": "qi-agent",
                    "status": "OPEN",
                }
            }
        }
    )
    model_called = False

    async def fake_draft(raw_goal: str) -> IntentDraft:
        nonlocal model_called
        model_called = True
        return draft_fixture()

    monkeypatch.setattr(web, "_store", lambda: store)
    monkeypatch.setattr(web, "draft_with_qi_agent", fake_draft)
    response = TestClient(web.app).post(
        "/api/intents/draft",
        json={
            "raw_goal": (
                "Find me a female ICML roommate in Seoul from July 6 to July 10."
            )
        },
    )
    assert response.status_code == 200
    assert model_called is True


def test_run_rejects_missing_published_qi_intent(monkeypatch) -> None:
    store = MemoryStore({})
    monkeypatch.setattr(web, "_store", lambda: store)
    response = TestClient(web.app).get(
        "/api/demo/run/stream?intent_id=intent_qi_missing"
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_safe_terminal_releases_only_current_run_capacity() -> None:
    store = MemoryStore({"intents": {}, "intent_pair_sessions": {}, "holds": {}})
    runtime = GoldenPathRuntime(
        store=store,  # type: ignore[arg-type]
        peer_base_url="https://peer.example",
        model_id="gemini-3.7-flash",
        source_intent_id="intent_qi",
    )
    run_id = str(runtime.run_id)
    store.collections["intents"] = {
        "intent_qi": {
            "intent_id": "intent_qi",
            "status": "NEGOTIATING",
            "active_run_id": run_id,
            "capacity_remaining": 1,
        },
        "intent_maya": {
            "intent_id": "intent_maya",
            "status": "NEGOTIATING",
            "active_run_id": run_id,
            "capacity_remaining": 1,
        },
        "intent_unrelated": {
            "intent_id": "intent_unrelated",
            "status": "NEGOTIATING",
            "active_run_id": "another-run",
            "capacity_remaining": 1,
        },
    }
    store.collections["intent_pair_sessions"]["pair-current"] = {
        "pair_session_id": "pair-current",
        "runId": run_id,
        "status": "ACTIVE",
    }
    store.collections["holds"]["hold-current"] = {
        "hold_id": "hold-current",
        "runId": run_id,
        "active": True,
        "status": "ACTIVE",
    }
    await runtime.release_run_negotiations(reason="no_progress")
    assert store.collections["intents"]["intent_qi"]["status"] == "OPEN"
    assert store.collections["intents"]["intent_maya"]["status"] == "OPEN"
    assert store.collections["intents"]["intent_unrelated"]["status"] == "NEGOTIATING"
    assert (
        store.collections["intent_pair_sessions"]["pair-current"]["status"]
        == "RELEASED"
    )
    assert store.collections["holds"]["hold-current"]["active"] is False


def revalidation_world(*, proposal_expired: bool = False) -> MemoryStore:
    now = datetime.now(UTC)
    proposal_id = "proposal-revalidate"
    run_id = "run-revalidate"
    pair_id = canonical_intent_pair("intent_qi", "intent_maya")
    return MemoryStore(
        {
            "approval_requests": {
                f"{proposal_id}-v1": {
                    "runId": run_id,
                    "proposalId": proposal_id,
                    "proposalVersion": 1,
                    "holdId": "hold-old",
                    "status": "AWAITING_HUMAN",
                    "disclosureHash": "a" * 64,
                }
            },
            "proposals": {
                proposal_id: {
                    "runId": run_id,
                    "proposal_id": proposal_id,
                    "version": 1,
                    "candidate_agent_id": "maya-agent",
                    "source_intent_id": "intent_qi",
                    "target_intent_id": "intent_maya",
                    "pair_session_id": pair_id,
                    "expires_at": (
                        now - timedelta(minutes=1)
                        if proposal_expired
                        else now + timedelta(minutes=10)
                    ).isoformat(),
                }
            },
            "holds": {
                "hold-old": {
                    "hold_id": "hold-old",
                    "active": True,
                    "status": "ACTIVE",
                    "expires_at": (now - timedelta(seconds=10)).isoformat(),
                }
            },
            "intents": {
                "intent_qi": {
                    "intent_id": "intent_qi",
                    "status": "AWAITING_APPROVAL",
                    "capacity_remaining": 1,
                },
                "intent_maya": {
                    "intent_id": "intent_maya",
                    "status": "AWAITING_APPROVAL",
                    "capacity_remaining": 1,
                },
            },
            "proposal_acceptances": {
                f"{proposal_id}-v1-qi-agent": {"proposalVersion": 1},
                f"{proposal_id}-v1-maya-agent": {"proposalVersion": 1},
            },
        }
    )


def test_expired_hold_requires_explicit_valid_revalidation(monkeypatch) -> None:
    store = revalidation_world()
    monkeypatch.setattr(web, "_store", lambda: store)
    response = TestClient(web.app).post(
        "/api/demo/revalidate",
        json={
            "run_id": "run-revalidate",
            "proposal_id": "proposal-revalidate",
            "proposal_version": 1,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REVALIDATED"
    assert store.collections["holds"]["hold-old"]["active"] is False
    renewed = [
        hold
        for hold_id, hold in store.collections["holds"].items()
        if hold_id != "hold-old"
    ]
    assert len(renewed) == 1
    assert renewed[0]["capacity_reserved"] == 1


def test_expired_proposal_is_not_revived(monkeypatch) -> None:
    store = revalidation_world(proposal_expired=True)
    monkeypatch.setattr(web, "_store", lambda: store)
    response = TestClient(web.app).post(
        "/api/demo/revalidate",
        json={
            "run_id": "run-revalidate",
            "proposal_id": "proposal-revalidate",
            "proposal_version": 1,
        },
    )
    assert response.status_code == 409
    assert set(store.collections["holds"]) == {"hold-old"}


def test_duplicate_human_approval_returns_existing_match(monkeypatch) -> None:
    disclosure = "a" * 64
    store = MemoryStore(
        {
            "approval_requests": {
                "proposal-committed-v1": {
                    "runId": "run-committed",
                    "proposalId": "proposal-committed",
                    "proposalVersion": 1,
                    "disclosureHash": disclosure,
                    "status": "APPROVED_AND_COMMITTED",
                }
            },
            "approvals": {
                "proposal-committed": {
                    "runId": "run-committed",
                    "proposalId": "proposal-committed",
                    "proposalVersion": 1,
                    "disclosureHash": disclosure,
                }
            },
            "matches": {
                "proposal-committed": {
                    "runId": "run-committed",
                    "proposalId": "proposal-committed",
                    "proposalVersion": 1,
                    "matchId": "proposal-committed",
                }
            },
        }
    )
    monkeypatch.setattr(web, "_store", lambda: store)
    response = TestClient(web.app).post(
        "/api/demo/approve",
        json={
            "run_id": "run-committed",
            "proposal_id": "proposal-committed",
            "proposal_version": 1,
            "confirmation": "APPROVE VERSION 1",
        },
    )
    assert response.status_code == 200
    assert response.json()["replayed"] is True
    assert response.json()["match"]["matchId"] == "proposal-committed"
    assert store.events == {}
