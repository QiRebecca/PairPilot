from datetime import UTC, datetime, timedelta

import pytest
from pairpilot_orchestrator.domain import AuthorityError, commit_approved_match


class FakeStore:
    def __init__(self, documents):
        self.documents = documents
        self.writes = []
        self.events = []

    async def get(self, collection, document_id):
        value = self.documents.get((collection, document_id))
        return dict(value) if value is not None else None

    def document_name(self, collection, document_id):
        return f"projects/test/databases/(default)/documents/{collection}/{document_id}"

    async def commit_writes(self, writes):
        self.writes = writes
        return {"commitTime": "2026-08-28T12:00:00Z"}

    async def write_event(self, **event):
        self.events.append(event)
        return {"event_id": "event", "published": True}


def world(*, hold_active=True, hold_expired=False):
    now = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)
    proposal_id = "proposal-1"
    run_id = "run-1"
    candidate = "maya-agent"
    version = 1
    request_id = f"{proposal_id}-v{version}"
    hold_id = "hold-1"
    update_time = "2026-08-28T11:59:00Z"
    return {
        ("proposals", proposal_id): {
            "proposal_id": proposal_id,
            "runId": run_id,
            "candidate_agent_id": candidate,
            "version": version,
            "shared_start": "2026-07-07",
            "shared_end": "2026-07-10",
            "solo_dates": ["2026-07-06"],
            "additional_cost_usd": 62,
            "delegated_maximum_usd": 70,
            "terms": ["equal split"],
            "disclosure_hash": "a" * 64,
            "expires_at": (now + timedelta(hours=1)).isoformat(),
            "status": "PROPOSED",
            "_updateTime": update_time,
        },
        ("approvals", proposal_id): {
            "proposalId": proposal_id,
            "proposalVersion": version,
            "disclosureHash": "a" * 64,
            "_updateTime": update_time,
        },
        ("runs", run_id): {
            "runId": run_id,
            "status": "WAITING_FOR_HUMAN_APPROVAL",
            "_updateTime": update_time,
        },
        ("approval_requests", request_id): {
            "runId": run_id,
            "proposalId": proposal_id,
            "proposalVersion": version,
            "holdId": hold_id,
            "status": "AWAITING_HUMAN",
            "_updateTime": update_time,
        },
        ("holds", hold_id): {
            "hold_id": hold_id,
            "proposal_id": proposal_id,
            "proposal_version": version,
            "active": hold_active,
            "expires_at": (
                now - timedelta(minutes=1)
                if hold_expired
                else now + timedelta(minutes=30)
            ).isoformat(),
            "_updateTime": update_time,
        },
        ("availability", candidate): {
            "candidateAgentId": candidate,
            "start": "2026-07-07",
            "end": "2026-07-10",
            "active": True,
            "version": 1,
            "_updateTime": update_time,
        },
        ("proposal_acceptances", f"{proposal_id}-v1-qi-agent"): {
            "proposalVersion": version,
            "agentId": "qi-agent",
            "_updateTime": update_time,
        },
        ("proposal_acceptances", f"{proposal_id}-v1-{candidate}"): {
            "proposalVersion": version,
            "agentId": candidate,
            "_updateTime": update_time,
        },
        (
            "relationships",
            "qi-agent__alice-agent__conference-coordination",
        ): {
            "sourceAgentId": "qi-agent",
            "targetAgentId": "alice-agent",
            "successfulIntroductions": 0,
            "provenanceEventIds": ["prior"],
            "_updateTime": update_time,
        },
    }


@pytest.mark.asyncio
async def test_atomic_commit_revalidates_and_builds_preconditioned_writes() -> None:
    store = FakeStore(world())
    match = await commit_approved_match(
        store=store,  # type: ignore[arg-type]
        run_id="run-1",
        proposal_id="proposal-1",
        now=datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
    )
    assert match["proposalVersion"] == 1
    assert len(store.writes) == 13
    assert store.writes[0]["currentDocument"] == {"exists": False}
    names = [write["update"]["name"] for write in store.writes]
    assert any("/matches/proposal-1" in name for name in names)
    assert any("/memories/" in name for name in names)
    assert any("/relationships/qi-agent__maya-agent" in name for name in names)
    assert store.events[0]["event_type"] == "match.committed"


@pytest.mark.asyncio
async def test_atomic_commit_rejects_expired_hold() -> None:
    store = FakeStore(world(hold_expired=True))
    with pytest.raises(AuthorityError, match="hold expired"):
        await commit_approved_match(
            store=store,  # type: ignore[arg-type]
            run_id="run-1",
            proposal_id="proposal-1",
            now=datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
        )
    assert store.writes == []
