"""Executable Startup V2 Match plans and participant-authorized actions."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from pairpilot_schemas import MatchState

from pairpilot_orchestrator.auth.authorization import require_match_participant
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.multi_user_platform import (
    PRODUCTION_NAMESPACE,
    SCHEMA_VERSION,
    stable_id,
)
from pairpilot_orchestrator.v1_foundation import create_notification
from pairpilot_orchestrator.v1_relationships import list_match_contact_cards


def _clean(document: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if not key.startswith("_")}


async def _owned_match(
    store: Any, principal: AuthenticatedPrincipal, match_id: str
) -> dict[str, Any]:
    match = await store.get("matches", match_id)
    if match is None or match.get("namespace") != PRODUCTION_NAMESPACE:
        raise LookupError("match was not found")
    require_match_participant(principal, match)
    return match


def _as_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime.combine(value, time(9), tzinfo=UTC)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(text), time(9), tzinfo=UTC)
        except ValueError:
            return None


def _plan_times(match: Mapping[str, Any]) -> tuple[datetime | None, datetime | None]:
    terms = match.get("terms") if isinstance(match.get("terms"), Mapping) else {}
    assert isinstance(terms, Mapping)
    start = _as_datetime(
        terms.get("start_at")
        or terms.get("date_start")
        or terms.get("date")
        or match.get("start_at")
    )
    end = _as_datetime(
        terms.get("end_at") or terms.get("date_end") or match.get("end_at")
    )
    if start and not end:
        end = start + timedelta(hours=1)
    if start and end and end <= start:
        end = start + timedelta(hours=1)
    return start, end


def canonical_match_state(
    match: Mapping[str, Any], *, now: datetime | None = None
) -> MatchState:
    explicit = str(match.get("state") or match.get("status") or "").upper()
    aliases = {
        "COMMITTED": MatchState.CONFIRMED,
        "MATCHED": MatchState.CONFIRMED,
        "AWAITING_HUMANS": MatchState.AWAITING_APPROVALS,
    }
    if explicit in aliases:
        state = aliases[explicit]
    else:
        try:
            state = MatchState(explicit) if explicit else MatchState.CONFIRMED
        except ValueError:
            state = MatchState.CONFIRMED
    if state in {MatchState.CANCELLED, MatchState.COMPLETED, MatchState.DISPUTED}:
        return state
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    start, end = _plan_times(match)
    if start and timestamp < start:
        return MatchState.UPCOMING
    if start and end and start <= timestamp < end:
        return MatchState.IN_PROGRESS
    if end and timestamp >= end:
        return MatchState.COMPLETED
    return state


def _match_projection(match: Mapping[str, Any]) -> dict[str, Any]:
    start, end = _plan_times(match)
    allowed = {
        "match_id",
        "proposal_id",
        "proposal_version",
        "participant_agent_ids",
        "source_intent_id",
        "target_intent_id",
        "community_id",
        "room_id",
        "terms",
        "committed_at",
        "updated_at",
        "cancelled_at",
        "cancelled_by_display_name",
        "cancellation_reason",
        "completed_at",
    }
    result = {key: value for key, value in match.items() if key in allowed}
    result.update(
        state=canonical_match_state(match).value,
        start_at=start,
        end_at=end,
    )
    return result


def _section(state: str) -> str:
    if state in {"PROPOSED", "AWAITING_APPROVALS", "CONFIRMED"}:
        return "NEEDS_ACTION"
    if state == "UPCOMING":
        return "UPCOMING"
    if state == "IN_PROGRESS":
        return "IN_PROGRESS"
    if state == "COMPLETED":
        return "COMPLETED"
    return "CANCELLED"


async def list_matches_for_user(
    store: Any, principal: AuthenticatedPrincipal
) -> dict[str, Any]:
    matches = await store.query_documents(
        "matches", filters=[("participant_uids", "ARRAY_CONTAINS", principal.uid)]
    )
    projections = [
        {
            **_match_projection(match),
            "section": _section(canonical_match_state(match).value),
        }
        for match in matches
        if match.get("namespace") == PRODUCTION_NAMESPACE
    ]
    projections.sort(key=lambda item: str(item.get("start_at") or ""))
    sections = {
        section: [item for item in projections if item["section"] == section]
        for section in (
            "NEEDS_ACTION",
            "UPCOMING",
            "IN_PROGRESS",
            "COMPLETED",
            "CANCELLED",
        )
    }
    return {"matches": projections, "sections": sections, "count": len(projections)}


async def get_match_detail(
    store: Any, principal: AuthenticatedPrincipal, match_id: str
) -> dict[str, Any]:
    match = await _owned_match(store, principal, match_id)
    uids = [str(item) for item in match.get("participant_uids", [])]
    (
        users,
        community,
        room,
        contact_cards,
        outcomes,
        changes,
        decisions,
    ) = await asyncio.gather(
        asyncio.gather(*(store.get("users", uid) for uid in uids)),
        store.get("communities", str(match.get("community_id") or ""))
        if match.get("community_id")
        else asyncio.sleep(0, result=None),
        store.get("coordination_rooms", str(match.get("room_id") or ""))
        if match.get("room_id")
        else asyncio.sleep(0, result=None),
        list_match_contact_cards(store, principal, match_id=match_id),
        store.query_documents("outcomes", filters=[("match_id", "EQUAL", match_id)]),
        store.query_documents(
            "match_change_proposals", filters=[("match_id", "EQUAL", match_id)]
        ),
        store.query_documents(
            "decisions", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
    )
    participants = [
        {
            "display_name": str((user or {}).get("display_name") or "Participant"),
            "personal_agent_id": str((user or {}).get("personal_agent_id") or ""),
            "is_viewer": uid == principal.uid,
        }
        for uid, user in zip(uids, users, strict=True)
    ]
    accepted = await store.query_documents(
        "contact_card_acceptances", filters=[("accepting_uid", "EQUAL", principal.uid)]
    )
    accepted_ids = {str(item.get("contact_card_id")) for item in accepted}
    cards = [
        {
            "contact_card_id": card.get("contact_card_id"),
            "display_name": card.get("display_name"),
            "fields": dict(card.get("fields") or {}),
            "status": card.get("status"),
            "offered_at": card.get("offered_at"),
            "is_viewer": card.get("owner_uid") == principal.uid,
            "accepted_by_viewer": card.get("contact_card_id") in accepted_ids,
        }
        for card in contact_cards
    ]
    projection = _match_projection(match)
    return {
        "match": projection,
        "participants": participants,
        "community": (
            {
                key: value
                for key, value in (community or {}).items()
                if key in {"community_id", "name", "location"}
            }
            if community
            else None
        ),
        "shared_room": (
            {
                key: value
                for key, value in (room or {}).items()
                if key
                in {"room_id", "room_type", "status", "human_participation_available"}
            }
            if room
            else None
        ),
        "approved_terms": dict(match.get("terms") or {}),
        "remaining_tasks": list(match.get("remaining_operational_tasks") or []),
        "contact_cards": cards,
        "calendar_available": _plan_times(match)[0] is not None,
        "cancellation": {
            "status": projection["state"],
            "reason": match.get("cancellation_reason"),
            "cancelled_at": match.get("cancelled_at"),
        },
        "backup": {
            "available": match.get("backup_available", True),
            "activated_at": match.get("backup_activated_at"),
        },
        "outcome_feedback_submitted": any(
            item.get("owner_uid") == principal.uid for item in outcomes
        ),
        "change_proposals": [
            {
                **{
                    key: value
                    for key, value in change.items()
                    if key
                    in {
                        "change_id",
                        "version",
                        "summary",
                        "terms",
                        "status",
                        "created_at",
                    }
                },
                "viewer_decision_status": next(
                    (
                        decision.get("status")
                        for decision in decisions
                        if decision.get("change_id") == change.get("change_id")
                    ),
                    "UNAVAILABLE",
                ),
            }
            for change in changes
        ],
        "safety_reminders": [
            "Meet in a public place and keep precise live location private.",
            "Only explicitly offered Contact Card fields are shared.",
            (
                "Report unsafe behavior; PairPilot does not verify identity or "
                "guarantee safety."
            ),
        ],
    }


def _ics_escape(value: object) -> str:
    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


async def build_match_calendar(
    store: Any, principal: AuthenticatedPrincipal, match_id: str
) -> str:
    match = await _owned_match(store, principal, match_id)
    start, end = _plan_times(match)
    if start is None or end is None:
        raise ValueError("match has no calendar-ready date and time")
    terms = dict(match.get("terms") or {})
    title = terms.get("title") or terms.get("event") or "PairPilot matched plan"
    location = terms.get("location") or "See PairPilot Shared Room"
    description = "; ".join(
        f"{key}: {value}"
        for key, value in terms.items()
        if key not in {"title", "event"}
    )
    uid = f"{match_id}@pairpilot"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//PairPilot//Startup V2//EN",
            "CALSCALE:GREGORIAN",
            "BEGIN:VEVENT",
            f"UID:{_ics_escape(uid)}",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{start.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}",
            f"DTEND:{end.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}",
            f"SUMMARY:{_ics_escape(title)}",
            f"LOCATION:{_ics_escape(location)}",
            f"DESCRIPTION:{_ics_escape(description)}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )


async def propose_match_change(
    store: Any,
    principal: AuthenticatedPrincipal,
    *,
    match_id: str,
    summary: str,
    terms: Mapping[str, str | int | bool],
) -> dict[str, Any]:
    match = await _owned_match(store, principal, match_id)
    if canonical_match_state(match) in {
        MatchState.CANCELLED,
        MatchState.COMPLETED,
    }:
        raise ValueError("closed matches cannot be changed")
    existing = await store.query_documents(
        "match_change_proposals", filters=[("match_id", "EQUAL", match_id)]
    )
    version = max([int(item.get("version", 1)) for item in existing], default=1) + 1
    change_id = stable_id("match_change", match_id, str(version))
    timestamp = datetime.now(UTC)
    change = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "change_id": change_id,
        "match_id": match_id,
        "version": version,
        "proposed_by_uid": principal.uid,
        "summary": summary,
        "terms": dict(terms),
        "status": "AWAITING_APPROVALS",
        "created_at": timestamp,
    }
    await store.create("match_change_proposals", change_id, change)
    for uid in match.get("participant_uids", []):
        decision_id = stable_id("decision_match_change", change_id, str(uid))
        await store.create(
            "decisions",
            decision_id,
            {
                "schema_version": SCHEMA_VERSION,
                "namespace": PRODUCTION_NAMESPACE,
                "decision_id": decision_id,
                "owner_uid": str(uid),
                "match_id": match_id,
                "change_id": change_id,
                "version": version,
                "type": "APPROVE_MATCH_CHANGE",
                "status": "OPEN",
                "title": "Review a proposed plan change",
                "summary": summary,
                "created_at": timestamp,
            },
        )
    return _clean(change)


async def approve_match_change(
    store: Any,
    principal: AuthenticatedPrincipal,
    *,
    match_id: str,
    change_id: str,
    version: int,
    confirmation: str,
) -> dict[str, Any]:
    match = await _owned_match(store, principal, match_id)
    change = await store.get("match_change_proposals", change_id)
    if change is None or change.get("match_id") != match_id:
        raise LookupError("match change was not found")
    if int(change.get("version", 0)) != version:
        raise ValueError("approval references an old change version")
    if confirmation != f"APPROVE CHANGE VERSION {version}":
        raise ValueError("exact current-version approval is required")
    if canonical_match_state(match) in {MatchState.CANCELLED, MatchState.COMPLETED}:
        raise ValueError("closed matches cannot be changed")
    decision_id = stable_id("decision_match_change", change_id, principal.uid)
    decision = await store.get("decisions", decision_id)
    if decision is None or decision.get("owner_uid") != principal.uid:
        raise PermissionError("change decision is not assigned to this participant")
    approval_id = stable_id("match_change_approval", change_id, principal.uid)
    timestamp = datetime.now(UTC)
    await store.create(
        "match_change_approvals",
        approval_id,
        {
            "schema_version": SCHEMA_VERSION,
            "namespace": PRODUCTION_NAMESPACE,
            "approval_id": approval_id,
            "change_id": change_id,
            "match_id": match_id,
            "version": version,
            "approving_uid": principal.uid,
            "approved_at": timestamp,
        },
    )
    clean_decision = _clean(decision)
    clean_decision.update(status="RESOLVED", resolved_at=timestamp)
    await store.upsert("decisions", decision_id, clean_decision)
    participant_uids = [str(uid) for uid in match.get("participant_uids", [])]
    approvals = await asyncio.gather(
        *(
            store.get(
                "match_change_approvals",
                stable_id("match_change_approval", change_id, uid),
            )
            for uid in participant_uids
        )
    )
    if any(approval is None for approval in approvals):
        return {
            "status": "WAITING_FOR_PEER",
            "change": _clean(change),
            "approvals_received": sum(approval is not None for approval in approvals),
            "approvals_required": len(participant_uids),
        }
    clean_match = _clean(match)
    current_version = int(clean_match.get("proposal_version", 1))
    if current_version < version:
        clean_match.update(
            terms={
                **dict(match.get("terms") or {}),
                **dict(change.get("terms") or {}),
            },
            proposal_version=version,
            status="COMMITTED",
            state="CONFIRMED",
            updated_at=timestamp,
        )
        await store.upsert("matches", match_id, clean_match)
    clean_change = _clean(change)
    clean_change.update(status="APPROVED", approved_at=timestamp)
    await store.upsert("match_change_proposals", change_id, clean_change)
    for uid in participant_uids:
        await create_notification(
            store,
            owner_uid=uid,
            notification_type="MATCH_PLAN_UPDATED",
            title="Both people approved the updated plan",
            body=f"Match version {version} is now authoritative.",
            entity_ids=[match_id, change_id],
            idempotency_key=f"match-change-approved:{change_id}:{uid}",
            now=timestamp,
        )
    return {
        "status": "MATCH_UPDATED",
        "change": clean_change,
        "match": _match_projection(clean_match),
    }


async def cancel_match(
    store: Any,
    principal: AuthenticatedPrincipal,
    *,
    match_id: str,
    reason: str,
    reopen_candidate_pool: bool,
) -> dict[str, Any]:
    match = await _owned_match(store, principal, match_id)
    if canonical_match_state(match) == MatchState.CANCELLED:
        return _match_projection(match)
    if canonical_match_state(match) == MatchState.COMPLETED:
        raise ValueError("completed matches cannot be cancelled")
    timestamp = datetime.now(UTC)
    profile = await store.get("users", principal.uid)
    clean = _clean(match)
    clean.update(
        status="CANCELLED",
        state="CANCELLED",
        cancellation_reason=reason,
        cancelled_by_uid=principal.uid,
        cancelled_by_display_name=str(
            (profile or {}).get("display_name") or "Participant"
        ),
        cancelled_at=timestamp,
        future_commitments_released=True,
        updated_at=timestamp,
    )
    await store.upsert("matches", match_id, clean)
    for uid in match.get("participant_uids", []):
        await create_notification(
            store,
            owner_uid=str(uid),
            notification_type="MATCH_CANCELLED",
            title="A matched plan was cancelled",
            body="Open Match Detail to review the cancellation and backup options.",
            entity_ids=[match_id, str(match.get("room_id") or "")],
            idempotency_key=f"match-cancelled:{match_id}:{uid}",
            now=timestamp,
        )
    event_id = stable_id("relationship_event", match_id, "cancelled", principal.uid)
    await store.create(
        "relationship_events",
        event_id,
        {
            "schema_version": SCHEMA_VERSION,
            "namespace": PRODUCTION_NAMESPACE,
            "relationship_event_id": event_id,
            "match_id": match_id,
            "owner_uid": principal.uid,
            "event_type": "MATCH_CANCELLED",
            "source": "MATCH_PARTICIPANT_ACTION",
            "created_at": timestamp,
        },
    )
    if reopen_candidate_pool:
        await store.write_event(
            event_type="match.backup_reactivation.requested.v2",
            run_id=match_id,
            producer=principal.uid,
            payload={"matchId": match_id, "requestingUid": principal.uid},
            idempotency_key=f"match:{match_id}:backup-reopen",
        )
    return _match_projection(clean)


async def activate_backup(
    store: Any, principal: AuthenticatedPrincipal, *, match_id: str
) -> dict[str, Any]:
    match = await _owned_match(store, principal, match_id)
    if canonical_match_state(match) != MatchState.CANCELLED:
        raise ValueError("backup activation requires a cancelled match")
    candidates = await store.query_documents(
        "candidate_assessments", filters=[("owner_uid", "EQUAL", principal.uid)]
    )
    backups = [item for item in candidates if item.get("state") == "BACKUP"]
    if not backups:
        raise LookupError("no backup candidate is available")
    selected = sorted(backups, key=lambda item: int(item.get("current_rank", 9999)))[0]
    clean_candidate = _clean(selected)
    clean_candidate.update(state="CONTACTING", updated_at=datetime.now(UTC))
    candidate_id = str(selected.get("assessment_id") or selected.get("_id"))
    await store.upsert("candidate_assessments", candidate_id, clean_candidate)
    clean_match = _clean(match)
    clean_match.update(backup_activated_at=datetime.now(UTC), backup_available=False)
    await store.upsert("matches", match_id, clean_match)
    await store.write_event(
        event_type="match.backup_activated.v2",
        run_id=match_id,
        producer=principal.uid,
        payload={
            "matchId": match_id,
            "candidateIntentId": selected.get("candidate_intent_id"),
        },
        idempotency_key=f"match:{match_id}:backup:{candidate_id}",
    )
    return {
        "match": _match_projection(clean_match),
        "candidate": {
            key: value
            for key, value in clean_candidate.items()
            if key
            in {
                "assessment_id",
                "candidate_intent_id",
                "candidate_display_name",
                "state",
            }
        },
    }


async def mark_match_completed(
    store: Any, principal: AuthenticatedPrincipal, *, match_id: str
) -> dict[str, Any]:
    match = await _owned_match(store, principal, match_id)
    if canonical_match_state(match) == MatchState.CANCELLED:
        raise ValueError("cancelled matches cannot be completed")
    clean = _clean(match)
    clean.update(status="COMPLETED", state="COMPLETED", completed_at=datetime.now(UTC))
    await store.upsert("matches", match_id, clean)
    return _match_projection(clean)


async def accept_contact_card(
    store: Any,
    principal: AuthenticatedPrincipal,
    *,
    match_id: str,
    contact_card_id: str,
) -> dict[str, Any]:
    await _owned_match(store, principal, match_id)
    card = await store.get("contact_cards", contact_card_id)
    if (
        card is None
        or card.get("match_id") != match_id
        or card.get("status") != "OFFERED"
        or not card.get("fields")
        or card.get("owner_uid") == principal.uid
    ):
        raise LookupError("contact card was not found")
    acceptance_id = stable_id("contact_acceptance", contact_card_id, principal.uid)
    acceptance = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "acceptance_id": acceptance_id,
        "contact_card_id": contact_card_id,
        "match_id": match_id,
        "accepting_uid": principal.uid,
        "status": "ACCEPTED",
        "accepted_at": datetime.now(UTC),
    }
    await store.create("contact_card_acceptances", acceptance_id, acceptance)
    return _clean(acceptance)
