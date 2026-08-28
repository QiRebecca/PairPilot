from typing import Any

from fastapi.testclient import TestClient
from pairpilot_orchestrator import web


class FakeStore:
    def __init__(self, collections: dict[str, list[dict[str, Any]]]) -> None:
        self.collections = collections

    async def list_documents(self, collection: str) -> list[dict[str, Any]]:
        return self.collections.get(collection, [])


async def test_public_state_exposes_no_private_profile_collection(monkeypatch) -> None:
    collections = {
        "runs": [
            {
                "runId": "run-1",
                "status": "RUNNING",
                "startedAt": "2026-08-28T18:00:00Z",
            }
        ],
        "agent_messages": [
            {
                "run_id": "run-1",
                "message_id": "message-1",
                "from_agent_id": "maya-agent",
                "to_agent_id": "qi-agent",
                "natural_language": "A quiet routine is preferred.",
                "speech_act": "INFORMATION_RESPONSE",
            }
        ],
    }
    monkeypatch.setattr(web, "_store", lambda: FakeStore(collections))
    state = await web.public_state("run-1")
    assert state["run"]["runId"] == "run-1"
    assert state["messages"][0]["claimsAreAuthoritativeFacts"] is False
    assert "agent_private_profiles" not in state
    assert "light sleeper" not in str(state).lower()


def test_approval_requires_exact_current_version_phrase(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    response = TestClient(web.app).post(
        "/api/demo/approve",
        json={
            "run_id": "run-1",
            "proposal_id": "proposal-1",
            "proposal_version": 2,
            "confirmation": "approve",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Exact current-version approval is required."


def test_health_discloses_exact_live_model(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-project")
    response = TestClient(web.app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["exactModelId"] == "gemini-3.7-flash"
    assert response.json()["executionMode"] == "LIVE GEMINI + GOOGLE ADK + A2A"
