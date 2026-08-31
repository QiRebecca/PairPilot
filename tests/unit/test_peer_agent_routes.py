import pytest
from google import genai
from pairpilot_peer_agents.a2a_executor import PeerAgentExecutor
from pairpilot_peer_agents.a2a_server import PEERS, create_app


def test_every_peer_has_independent_card_route_and_rpc_route() -> None:
    app = create_app(
        base_url="https://peer.example",
        project_id="test-project",
        model_id="gemini-3.7-flash",
        location="global",
    )
    route_paths = [route.path for route in app.routes]
    for peer in PEERS:
        assert f"/.well-known/agents/{peer.agent_id}.json" in route_paths
        assert f"/a2a/{peer.slug}" in route_paths
    assert set(app.state.a2a_handlers) == {
        "alice-agent",
        "maya-agent",
        "lena-agent",
    }
    assert len({id(value) for value in app.state.a2a_handlers.values()}) == 3
    assert len({id(value) for value in app.state.provenance_stores.values()}) == 3


class _ExhaustedRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run_async(self, **_kwargs):
        self.calls += 1

        async def events():
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
            yield

        return events()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("agent_id", "expected_action", "expected_speech_act"),
    [
        ("alice-agent", "DECLINE_INTRODUCTION", "INTRODUCTION_RESPONSE"),
        ("maya-agent", "PROVIDE_INFORMATION", "INFORMATION_RESPONSE"),
    ],
)
async def test_peer_model_exhaustion_returns_explicit_safe_nonresponse(
    monkeypatch: pytest.MonkeyPatch,
    agent_id: str,
    expected_action: str,
    expected_speech_act: str,
) -> None:
    executor = object.__new__(PeerAgentExecutor)
    executor.agent_id = agent_id
    executor.owner_id = f"owner-{agent_id}"
    runner = _ExhaustedRunner()
    executor._runner = runner

    async def no_delay(_seconds: float) -> None:
        return None

    monkeypatch.setattr("pairpilot_peer_agents.a2a_executor.asyncio.sleep", no_delay)
    decision, live_model_output = await executor._generate_decision(
        session_id="session-qa",
        user_message=genai.types.Content(
            role="user", parts=[genai.types.Part(text="bounded test request")]
        ),
    )

    assert live_model_output is False
    assert decision.action == expected_action
    assert decision.speech_act == expected_speech_act
    assert decision.confidence == 0
    assert decision.claims == []
    assert decision.reason == "MODEL_NO_VALID_OUTPUT_AFTER_BOUNDED_RETRIES"
    assert runner.calls == executor.MAX_RUNTIME_ATTEMPTS
