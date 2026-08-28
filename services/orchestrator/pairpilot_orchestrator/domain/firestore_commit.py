"""Atomic Firestore commitment after explicit current human approval."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from pairpilot_orchestrator.domain.authority import AuthorityError
from pairpilot_orchestrator.infrastructure.google_cloud import (
    GoogleCloudStore,
    encode_fields,
)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise AuthorityError("authoritative timestamp is missing")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _clean(document: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if not key.startswith("_")}


def _update_write(
    store: GoogleCloudStore,
    *,
    collection: str,
    document_id: str,
    data: dict[str, Any],
    update_time: str | None = None,
    exists: bool | None = None,
) -> dict[str, Any]:
    write: dict[str, Any] = {
        "update": {
            "name": store.document_name(collection, document_id),
            "fields": encode_fields(data),
        }
    }
    if update_time is not None:
        write["currentDocument"] = {"updateTime": update_time}
    elif exists is not None:
        write["currentDocument"] = {"exists": exists}
    return write


async def create_human_approval(
    *,
    store: GoogleCloudStore,
    run_id: str,
    proposal_id: str,
    proposal_version: int,
    disclosure_hash: str,
) -> dict[str, Any]:
    """Persist the user's explicit approval of one displayed effect contract."""

    request_id = f"{proposal_id}-v{proposal_version}"
    request = await store.get("approval_requests", request_id)
    if request is None or request.get("runId") != run_id:
        raise AuthorityError("current approval request does not exist")
    if request.get("status") != "AWAITING_HUMAN":
        raise AuthorityError("approval request is not awaiting the user")
    if int(request.get("proposalVersion", 0)) != proposal_version:
        raise AuthorityError("approval references an old proposal version")
    if request.get("disclosureHash") != disclosure_hash:
        raise AuthorityError("displayed disclosure scope does not match")
    approval = {
        "approvalId": str(uuid4()),
        "runId": run_id,
        "proposalId": proposal_id,
        "proposalVersion": proposal_version,
        "disclosureHash": disclosure_hash,
        "approvedAt": datetime.now(UTC),
        "source": "explicit_human_effect_contract",
    }
    created = await store.create("approvals", proposal_id, approval)
    if not created:
        existing = await store.get("approvals", proposal_id)
        if existing is None:
            raise AuthorityError("approval disappeared during idempotency check")
        if (
            int(existing.get("proposalVersion", 0)) != proposal_version
            or existing.get("disclosureHash") != disclosure_hash
        ):
            raise AuthorityError("a conflicting approval already exists")
        return existing
    await store.write_event(
        event_type="approval.received",
        run_id=run_id,
        producer="human-user",
        payload={"proposalId": proposal_id, "proposalVersion": proposal_version},
        idempotency_key=f"{run_id}:approval.received:{proposal_id}:v{proposal_version}",
    )
    return approval


async def commit_approved_match(
    *,
    store: GoogleCloudStore,
    run_id: str,
    proposal_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Revalidate every authority input and atomically commit one match."""

    commit_time = (now or datetime.now(UTC)).astimezone(UTC)
    existing_match = await store.get("matches", proposal_id)
    if existing_match is not None:
        return existing_match

    proposal = await store.get("proposals", proposal_id)
    approval = await store.get("approvals", proposal_id)
    run = await store.get("runs", run_id)
    if proposal is None or approval is None or run is None:
        raise AuthorityError("proposal, approval, and run are required")
    version = int(proposal["version"])
    candidate = str(proposal["candidate_agent_id"])
    if proposal.get("runId") != run_id:
        raise AuthorityError("proposal belongs to another run")
    if _timestamp(proposal["expires_at"]) <= commit_time:
        raise AuthorityError("proposal expired")
    if int(approval["proposalVersion"]) != version:
        raise AuthorityError("approval references an old proposal version")
    if approval["disclosureHash"] != proposal["disclosure_hash"]:
        raise AuthorityError("disclosure scope changed after approval")

    request_id = f"{proposal_id}-v{version}"
    request = await store.get("approval_requests", request_id)
    if request is None:
        raise AuthorityError("effect contract is missing")
    hold_id = str(request["holdId"])
    hold = await store.get("holds", hold_id)
    availability = await store.get("availability", candidate)
    qi_acceptance_id = f"{proposal_id}-v{version}-qi-agent"
    peer_acceptance_id = f"{proposal_id}-v{version}-{candidate}"
    qi_acceptance = await store.get("proposal_acceptances", qi_acceptance_id)
    peer_acceptance = await store.get("proposal_acceptances", peer_acceptance_id)
    alice_id = "qi-agent__alice-agent__conference-coordination"
    alice = await store.get("relationships", alice_id)
    if any(
        item is None
        for item in (hold, availability, qi_acceptance, peer_acceptance, alice)
    ):
        raise AuthorityError(
            "hold, availability, both acceptances, and provenance are required"
        )
    assert hold is not None
    assert availability is not None
    assert qi_acceptance is not None
    assert peer_acceptance is not None
    assert alice is not None
    if not bool(hold["active"]) or int(hold["proposal_version"]) != version:
        raise AuthorityError("active current hold required")
    if _timestamp(hold["expires_at"]) <= commit_time:
        raise AuthorityError("hold expired")
    if not bool(availability["active"]):
        raise AuthorityError("candidate is no longer available")
    shared_start = date.fromisoformat(str(proposal["shared_start"]))
    shared_end = date.fromisoformat(str(proposal["shared_end"]))
    if not (
        date.fromisoformat(str(availability["start"])) <= shared_start
        and date.fromisoformat(str(availability["end"])) >= shared_end
    ):
        raise AuthorityError("candidate availability changed")
    for acceptance in (qi_acceptance, peer_acceptance):
        if int(acceptance["proposalVersion"]) != version:
            raise AuthorityError("both personal agents must accept current version")

    update_times = {
        "proposal": proposal.get("_updateTime"),
        "approval": approval.get("_updateTime"),
        "run": run.get("_updateTime"),
        "request": request.get("_updateTime"),
        "hold": hold.get("_updateTime"),
        "availability": availability.get("_updateTime"),
        "qi": qi_acceptance.get("_updateTime"),
        "peer": peer_acceptance.get("_updateTime"),
        "alice": alice.get("_updateTime"),
    }
    if not all(update_times.values()):
        raise AuthorityError("commit precondition metadata is missing")

    event_id = str(uuid4())
    memory_id = str(uuid4())
    relationship_id = f"qi-agent__{candidate}__conference-roommate-coordination"
    match = {
        "matchId": proposal_id,
        "runId": run_id,
        "proposalId": proposal_id,
        "proposalVersion": version,
        "candidateAgentId": candidate,
        "committedAt": commit_time,
        "provenanceEventIds": [event_id],
    }
    updated_hold = _clean(hold)
    updated_hold.update(
        active=False, releasedAt=commit_time, releaseReason="match_committed"
    )
    updated_proposal = _clean(proposal)
    updated_proposal["status"] = "COMMITTED"
    updated_run = _clean(run)
    updated_run.update(
        status="COMMITTED", committedMatchId=proposal_id, completedAt=commit_time
    )
    updated_request = _clean(request)
    updated_request.update(status="APPROVED_AND_COMMITTED", committedAt=commit_time)
    updated_alice = _clean(alice)
    updated_alice["successfulIntroductions"] = (
        int(updated_alice.get("successfulIntroductions", 0)) + 1
    )
    updated_alice["provenanceEventIds"] = list(
        updated_alice.get("provenanceEventIds", [])
    ) + [event_id]
    updated_alice["updatedAt"] = commit_time
    relationship = {
        "sourceAgentId": "qi-agent",
        "targetAgentId": candidate,
        "context": "conference_roommate_coordination",
        "relationType": "successful_coordination",
        "coordinationReliability": 0.8,
        "responseReliability": 1.0,
        "privacyRespect": 1.0,
        "successfulPlans": 1,
        "successfulIntroductions": 0,
        "provenanceEventIds": [event_id],
        "updatedAt": commit_time,
    }
    memory = {
        "memoryId": memory_id,
        "ownerAgentId": "qi-agent",
        "memoryType": "inferred_preference",
        "content": (
            "The user accepted partial date coverage to preserve "
            "quiet-room compatibility."
        ),
        "scope": "hotel_sharing",
        "source": "approved_successful_coordination",
        "confidence": 0.78,
        "sensitivity": "personal_preference",
        "confirmationStatus": "editable_inference",
        "provenanceEventIds": [event_id],
        "createdAt": commit_time,
        "lastConfirmedAt": None,
        "decayPolicy": "review_after_180_days",
    }
    relationship_event = {
        "eventId": event_id,
        "eventType": "successful_coordination",
        "runId": run_id,
        "participants": ["qi-agent", candidate],
        "proposalId": proposal_id,
        "occurredAt": commit_time,
    }
    writes = [
        _update_write(
            store,
            collection="matches",
            document_id=proposal_id,
            data=match,
            exists=False,
        ),
        _update_write(
            store,
            collection="holds",
            document_id=hold_id,
            data=updated_hold,
            update_time=str(update_times["hold"]),
        ),
        _update_write(
            store,
            collection="proposals",
            document_id=proposal_id,
            data=updated_proposal,
            update_time=str(update_times["proposal"]),
        ),
        _update_write(
            store,
            collection="runs",
            document_id=run_id,
            data=updated_run,
            update_time=str(update_times["run"]),
        ),
        _update_write(
            store,
            collection="approval_requests",
            document_id=request_id,
            data=updated_request,
            update_time=str(update_times["request"]),
        ),
        _update_write(
            store,
            collection="relationships",
            document_id=alice_id,
            data=updated_alice,
            update_time=str(update_times["alice"]),
        ),
        _update_write(
            store,
            collection="relationships",
            document_id=relationship_id,
            data=relationship,
            exists=False,
        ),
        _update_write(
            store,
            collection="relationship_events",
            document_id=event_id,
            data=relationship_event,
            exists=False,
        ),
        _update_write(
            store,
            collection="memories",
            document_id=memory_id,
            data=memory,
            exists=False,
        ),
    ]
    # No-op writes add atomic update-time preconditions for read-only authority.
    for label, collection, document_id, document in (
        ("availability", "availability", candidate, availability),
        ("approval", "approvals", proposal_id, approval),
        ("qi", "proposal_acceptances", qi_acceptance_id, qi_acceptance),
        ("peer", "proposal_acceptances", peer_acceptance_id, peer_acceptance),
    ):
        writes.append(
            _update_write(
                store,
                collection=collection,
                document_id=document_id,
                data=_clean(document),
                update_time=str(update_times[label]),
            )
        )
    await store.commit_writes(writes)
    await store.write_event(
        event_type="match.committed",
        run_id=run_id,
        producer="commit-authority",
        payload={
            "matchId": proposal_id,
            "proposalId": proposal_id,
            "proposalVersion": version,
        },
        idempotency_key=f"{run_id}:match.committed:{proposal_id}:v{version}",
    )
    return match
