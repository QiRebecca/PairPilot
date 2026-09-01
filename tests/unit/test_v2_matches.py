from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.v2_matches import (
    accept_contact_card,
    activate_backup,
    approve_match_change,
    build_match_calendar,
    cancel_match,
    canonical_match_state,
    get_match_detail,
    list_matches_for_user,
    mark_match_completed,
    propose_match_change,
)
from pairpilot_schemas import MatchState
from test_multi_user_platform import MemoryMultiUserStore


def principal(uid: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        uid=uid,
        email=f"{uid}@example.com",
        email_verified=True,
    )


async def seed_match(
    store: MemoryMultiUserStore,
    *,
    status: str = "COMMITTED",
    date_start: str = "2030-09-20T08:30:00+00:00",
) -> None:
    for uid in ("viewer", "peer"):
        await store.create(
            "users",
            uid,
            {
                "namespace": "production",
                "uid": uid,
                "display_name": uid.title(),
                "email": f"{uid}@private.example",
                "personal_agent_id": f"agent_{uid}",
            },
        )
    await store.create(
        "communities",
        "community_builders",
        {
            "namespace": "production",
            "community_id": "community_builders",
            "name": "Agent Builders",
            "location": "Global",
        },
    )
    await store.create(
        "coordination_rooms",
        "room_match",
        {
            "namespace": "production",
            "room_id": "room_match",
            "participant_uids": ["viewer", "peer"],
            "room_type": "SHARED_COORDINATION_ROOM",
            "status": "ACTIVE",
            "human_participation_available": True,
        },
    )
    await store.create(
        "matches",
        "match_pair",
        {
            "schema_version": 4,
            "namespace": "production",
            "match_id": "match_pair",
            "proposal_id": "proposal_pair",
            "proposal_version": 1,
            "source_intent_id": "intent_viewer",
            "target_intent_id": "intent_peer",
            "participant_uids": ["viewer", "peer"],
            "participant_agent_ids": ["agent_viewer", "agent_peer"],
            "community_id": "community_builders",
            "room_id": "room_match",
            "status": status,
            "terms": {
                "title": "Agent systems working session",
                "date_start": date_start,
                "end_at": "2030-09-20T10:00:00+00:00",
                "location": "Public conference lobby",
                "expenses": "Individual",
            },
            "committed_at": datetime(2026, 9, 1, tzinfo=UTC),
        },
    )
    await store.create(
        "task_workspaces",
        "task_viewer",
        {
            "namespace": "production",
            "task_id": "task_viewer",
            "intent_id": "intent_viewer",
            "owner_uid": "viewer",
        },
    )


@pytest.mark.asyncio
async def test_match_list_and_detail_are_participant_scoped_and_private_safe() -> None:
    store = MemoryMultiUserStore()
    await seed_match(store)

    listing = await list_matches_for_user(store, principal("viewer"))
    detail = await get_match_detail(store, principal("viewer"), "match_pair")

    assert listing["count"] == 1
    assert listing["sections"]["UPCOMING"][0]["match_id"] == "match_pair"
    assert detail["participants"][0]["display_name"] == "Viewer"
    assert detail["community"]["name"] == "Agent Builders"
    assert detail["shared_room"]["room_id"] == "room_match"
    assert detail["calendar_available"] is True
    assert "@private.example" not in str(detail)
    assert "participant_uids" not in str(detail)
    assert "owner_uid" not in str(detail)
    with pytest.raises(HTTPException) as denied:
        await get_match_detail(store, principal("outsider"), "match_pair")
    assert denied.value.status_code == 403


@pytest.mark.asyncio
async def test_calendar_export_is_valid_escaped_utc_ics() -> None:
    store = MemoryMultiUserStore()
    await seed_match(store)
    calendar = await build_match_calendar(store, principal("viewer"), "match_pair")
    assert calendar.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0")
    assert "BEGIN:VEVENT" in calendar
    assert "DTSTART:20300920T083000Z" in calendar
    assert "DTEND:20300920T100000Z" in calendar
    assert "SUMMARY:Agent systems working session" in calendar
    assert calendar.endswith("END:VCALENDAR\r\n")


@pytest.mark.asyncio
async def test_material_change_creates_new_version_and_two_decisions() -> None:
    store = MemoryMultiUserStore()
    await seed_match(store)
    original = await store.get("matches", "match_pair")
    assert original is not None

    change = await propose_match_change(
        store,
        principal("viewer"),
        match_id="match_pair",
        summary="Move the session thirty minutes later.",
        terms={"start_at": "2030-09-20T09:00:00+00:00"},
    )

    assert change["version"] == 2
    assert change["status"] == "AWAITING_APPROVALS"
    assert len(store.collections["decisions"]) == 2
    persisted = await store.get("matches", "match_pair")
    assert persisted is not None
    assert persisted["terms"] == original["terms"]

    waiting = await approve_match_change(
        store,
        principal("viewer"),
        match_id="match_pair",
        change_id=change["change_id"],
        version=2,
        confirmation="APPROVE CHANGE VERSION 2",
    )
    assert waiting["status"] == "WAITING_FOR_PEER"
    unchanged = await store.get("matches", "match_pair")
    assert unchanged is not None
    assert unchanged["terms"] == original["terms"]

    committed = await approve_match_change(
        store,
        principal("peer"),
        match_id="match_pair",
        change_id=change["change_id"],
        version=2,
        confirmation="APPROVE CHANGE VERSION 2",
    )
    assert committed["status"] == "MATCH_UPDATED"
    updated = await store.get("matches", "match_pair")
    assert updated is not None
    assert updated["proposal_version"] == 2
    assert updated["terms"]["start_at"] == "2030-09-20T09:00:00+00:00"


@pytest.mark.asyncio
async def test_cancellation_is_audited_notified_and_requests_backup_reopen() -> None:
    store = MemoryMultiUserStore()
    await seed_match(store)
    cancelled = await cancel_match(
        store,
        principal("viewer"),
        match_id="match_pair",
        reason="Travel plans changed.",
        reopen_candidate_pool=True,
    )
    assert cancelled["state"] == "CANCELLED"
    assert cancelled["cancellation_reason"] == "Travel plans changed."
    assert len(store.collections["notifications"]) == 2
    assert len(store.collections["relationship_events"]) == 1
    events = list(store.collections["events"].values())
    assert events[0]["eventType"] == "match.backup_reactivation.requested.v2"
    assert (
        await cancel_match(
            store,
            principal("viewer"),
            match_id="match_pair",
            reason="Repeated cancellation is idempotent.",
            reopen_candidate_pool=True,
        )
        == cancelled
    )


@pytest.mark.asyncio
async def test_backup_activation_requires_cancelled_match_and_uses_best_backup() -> (
    None
):
    store = MemoryMultiUserStore()
    await seed_match(store)
    with pytest.raises(ValueError, match="cancelled match"):
        await activate_backup(store, principal("viewer"), match_id="match_pair")
    await cancel_match(
        store,
        principal("viewer"),
        match_id="match_pair",
        reason="Peer unavailable.",
        reopen_candidate_pool=False,
    )
    for rank, task_id in ((2, "task_viewer"), (1, "unrelated_task")):
        await store.create(
            "candidate_assessments",
            f"candidate_{rank}",
            {
                "assessment_id": f"candidate_{rank}",
                "owner_uid": "viewer",
                "task_id": task_id,
                "candidate_intent_id": f"intent_backup_{rank}",
                "candidate_display_name": f"Backup {rank}",
                "current_rank": rank,
                "state": "BACKUP",
            },
        )
    activated = await activate_backup(store, principal("viewer"), match_id="match_pair")
    assert activated["candidate"]["candidate_intent_id"] == "intent_backup_2"
    assert activated["candidate"]["state"] == "CONTACTING"


@pytest.mark.asyncio
async def test_contact_acceptance_and_completion_are_explicit() -> None:
    store = MemoryMultiUserStore()
    await seed_match(store)
    await store.create(
        "contact_cards",
        "card_peer",
        {
            "contact_card_id": "card_peer",
            "namespace": "production",
            "match_id": "match_pair",
            "owner_uid": "peer",
            "status": "OFFERED",
            "fields": {"signal": "peer-signal"},
        },
    )
    accepted = await accept_contact_card(
        store,
        principal("viewer"),
        match_id="match_pair",
        contact_card_id="card_peer",
    )
    assert accepted["status"] == "ACCEPTED"
    completed = await mark_match_completed(
        store, principal("viewer"), match_id="match_pair"
    )
    assert completed["state"] == "COMPLETED"
    assert (
        canonical_match_state(store.collections["matches"]["match_pair"])
        == MatchState.COMPLETED
    )
