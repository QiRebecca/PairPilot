import pytest
from pairpilot_orchestrator.workflow import GoldenPathRuntime


def runtime() -> GoldenPathRuntime:
    return GoldenPathRuntime(
        store=object(),  # type: ignore[arg-type]
        peer_base_url="https://peer.example",
        model_id="gemini-3.7-flash",
        source_intent_id="intent_qi_test",
    )


def test_tool_surface_uses_batch_contact_instead_of_single_contact() -> None:
    names = [tool.__name__ for tool in runtime().tools()]
    assert "contact_candidates" in names
    assert "contact_candidate" not in names
    assert "search_open_intents" in names
    assert "search_open_agents" not in names


@pytest.mark.asyncio
async def test_candidate_contact_batch_is_bounded_to_two() -> None:
    with pytest.raises(ValueError, match="one or two"):
        await runtime().contact_candidates(
            ["a-agent", "b-agent", "c-agent"],
            "What overnight routine could affect a shared room?",
        )


@pytest.mark.asyncio
async def test_candidate_contact_batch_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        await runtime().contact_candidates(
            ["maya-agent", "maya-agent"],
            "What overnight routine could affect a shared room?",
        )


@pytest.mark.asyncio
async def test_candidate_contact_batch_preserves_partial_success() -> None:
    item = runtime()
    item.discovered_intents = {
        "intent_maya": "maya-agent",
        "intent_lena": "lena-agent",
    }

    async def fake_contact(intent_id: str, question: str) -> dict[str, str]:
        assert question
        if intent_id == "intent_maya":
            return {"target_intent_id": intent_id, "status": "received"}
        raise RuntimeError("transient peer output failure")

    async def fake_observe(**kwargs: object) -> dict[str, object]:
        return kwargs["result"]  # type: ignore[return-value]

    item._contact_candidate = fake_contact  # type: ignore[method-assign]
    item._observe = fake_observe  # type: ignore[method-assign]
    result = await item.contact_candidates(
        ["intent_maya", "intent_lena"],
        "What overnight routine could affect a shared room?",
    )
    assert result["candidate_responses"] == [
        {"target_intent_id": "intent_maya", "status": "received"}
    ]
    assert result["contact_errors"] == [
        {
            "target_intent_id": "intent_lena",
            "error_type": "RuntimeError",
            "recovery": "retry_this_intent_or_terminate_safely",
        }
    ]
