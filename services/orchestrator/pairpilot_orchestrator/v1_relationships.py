"""Match-scoped contact exchange and authoritative outcome intelligence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pairpilot_schemas import ContactCardInput, OutcomeCheckInInput

from pairpilot_orchestrator.auth.authorization import require_match_participant
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.multi_user_platform import (
    PRODUCTION_NAMESPACE,
    SCHEMA_VERSION,
    MultiUserStore,
    _clean,
    stable_id,
)
from pairpilot_orchestrator.v1_foundation import create_notification


async def _owned_match(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    match_id: str,
) -> dict[str, Any]:
    match = await store.get("matches", match_id)
    if match is None or match.get("namespace") != PRODUCTION_NAMESPACE:
        raise LookupError("match was not found")
    require_match_participant(principal, match)
    return match


async def offer_contact_card(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    match_id: str,
    body: ContactCardInput,
    now: datetime | None = None,
) -> dict[str, Any]:
    match = await _owned_match(store, principal, match_id)
    fields = {
        key: value.strip()
        for key, value in body.model_dump().items()
        if isinstance(value, str) and value.strip()
    }
    if not fields:
        raise ValueError("at least one contact field must be explicitly offered")
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    card_id = stable_id("contact_card", match_id, principal.uid)
    profile = await store.get("users", principal.uid)
    card = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "contact_card_id": card_id,
        "match_id": match_id,
        "room_id": match.get("room_id"),
        "owner_uid": principal.uid,
        "display_name": str((profile or {}).get("display_name", "Matched member")),
        "fields": fields,
        "status": "OFFERED",
        "offered_at": timestamp,
        "updated_at": timestamp,
    }
    await store.upsert("contact_cards", card_id, card)
    for peer_uid in match.get("participant_uids", []):
        if str(peer_uid) == principal.uid:
            continue
        await create_notification(
            store,
            owner_uid=str(peer_uid),
            notification_type="CONTACT_CARD_OFFERED",
            title="A matched connection offered contact details",
            body="Open the shared room to review the explicitly offered fields.",
            entity_ids=[match_id, str(match.get("room_id", "")), card_id],
            idempotency_key=f"contact-card:{card_id}:{timestamp.isoformat()}",
            now=timestamp,
        )
    return card


async def revoke_contact_card(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    match_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    await _owned_match(store, principal, match_id)
    card_id = stable_id("contact_card", match_id, principal.uid)
    card = await store.get("contact_cards", card_id)
    if card is None:
        raise LookupError("contact card was not found")
    clean = _clean(card)
    clean.update(
        fields={},
        status="REVOKED",
        revoked_at=now or datetime.now(UTC),
        updated_at=now or datetime.now(UTC),
    )
    await store.upsert("contact_cards", card_id, clean)
    return clean


async def list_match_contact_cards(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    match_id: str,
) -> list[dict[str, Any]]:
    await _owned_match(store, principal, match_id)
    cards = await store.query_documents(
        "contact_cards", filters=[("match_id", "EQUAL", match_id)]
    )
    return [
        _clean(card)
        for card in cards
        if card.get("status") == "OFFERED" and card.get("fields")
    ]


async def submit_outcome_check_in(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    match_id: str,
    body: OutcomeCheckInInput,
    now: datetime | None = None,
) -> dict[str, Any]:
    match = await _owned_match(store, principal, match_id)
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    outcome_id = stable_id("outcome", match_id, principal.uid)
    existing = await store.get("outcomes", outcome_id)
    if existing is not None:
        return _clean(existing)
    participant_uids = [str(item) for item in match.get("participant_uids", [])]
    participant_agents = [str(item) for item in match.get("participant_agent_ids", [])]
    own_index = participant_uids.index(principal.uid)
    peer_agent_id = participant_agents[1 - own_index]
    relationship_id = stable_id("relationship", principal.uid, peer_agent_id)
    relationship = await store.get("relationships", relationship_id)
    if relationship is None:
        raise RuntimeError("match relationship was not found")
    event_id = stable_id("relationship_event", match_id, principal.uid, "outcome")
    outcome = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "outcome_id": outcome_id,
        "owner_uid": principal.uid,
        "match_id": match_id,
        "did_plan_happen": body.did_plan_happen,
        "would_coordinate_again": body.would_coordinate_again,
        "agreed_term_inaccurate": body.agreed_term_inaccurate,
        "optional_feedback_private": body.optional_feedback,
        "relationship_event_id": event_id,
        "created_at": timestamp,
    }
    event = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "relationship_event_id": event_id,
        "relationship_id": relationship_id,
        "owner_uid": principal.uid,
        "match_id": match_id,
        "event_type": "AUTHORITATIVE_OWNER_OUTCOME",
        "did_plan_happen": body.did_plan_happen,
        "would_coordinate_again": body.would_coordinate_again,
        "agreed_term_inaccurate": body.agreed_term_inaccurate,
        "source": "MATCH_PARTICIPANT_CHECK_IN",
        "created_at": timestamp,
    }
    clean_relationship = _clean(relationship)
    clean_relationship.update(
        plans_reported=int(clean_relationship.get("plans_reported", 0)) + 1,
        successful_plans=int(clean_relationship.get("successful_plans", 0))
        + (1 if body.did_plan_happen else 0),
        cancellation_history=int(clean_relationship.get("cancellation_history", 0))
        + (0 if body.did_plan_happen else 1),
        commitment_inaccuracy_reports=int(
            clean_relationship.get("commitment_inaccuracy_reports", 0)
        )
        + (1 if body.agreed_term_inaccurate else 0),
        would_coordinate_again_yes=int(
            clean_relationship.get("would_coordinate_again_yes", 0)
        )
        + (1 if body.would_coordinate_again else 0),
        last_interaction_at=timestamp,
        updated_at=timestamp,
    )
    await store.create("outcomes", outcome_id, outcome)
    await store.create("relationship_events", event_id, event)
    await store.upsert("relationships", relationship_id, clean_relationship)
    memory_id = stable_id("memory", match_id, principal.uid, "outcome")
    await store.create(
        "memories",
        memory_id,
        {
            "schema_version": SCHEMA_VERSION,
            "namespace": PRODUCTION_NAMESPACE,
            "memory_id": memory_id,
            "owner_uid": principal.uid,
            "owner_agent_id": participant_agents[own_index],
            "memory_type": "EPISODIC_OUTCOME",
            "content": (
                "A matched plan happened."
                if body.did_plan_happen
                else "A matched plan did not happen."
            ),
            "scope": "RELATIONSHIP_AND_TASK_TYPE",
            "source": "authoritative_owner_outcome",
            "confidence": "AUTHORITATIVE_OWNER_REPORT",
            "sensitivity": "PRIVATE",
            "status": "PROPOSED",
            "confirmation_status": "REVIEWABLE",
            "provenance_event_ids": [event_id],
            "match_id": match_id,
            "created_at": timestamp,
        },
    )
    if body.agreed_term_inaccurate:
        signal_id = stable_id("moderation_signal", outcome_id, "inaccurate-term")
        await store.create(
            "moderation_signals",
            signal_id,
            {
                "schema_version": SCHEMA_VERSION,
                "namespace": PRODUCTION_NAMESPACE,
                "signal_id": signal_id,
                "owner_uid": principal.uid,
                "match_id": match_id,
                "type": "AGREED_TERM_REPORTED_INACCURATE",
                "status": "UNREVIEWED",
                "created_at": timestamp,
            },
        )
    await store.write_event(
        event_type="product.match_outcome_recorded.v1",
        run_id=match_id,
        producer=principal.uid,
        payload={
            "matchId": match_id,
            "didPlanHappen": body.did_plan_happen,
            "wouldCoordinateAgain": body.would_coordinate_again,
        },
        idempotency_key=f"outcome:{outcome_id}:recorded",
        publish_immediately=False,
    )
    return outcome
