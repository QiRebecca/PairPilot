import pytest
from pairpilot_orchestrator.workflow import GoldenPathRuntime


def runtime() -> GoldenPathRuntime:
    return GoldenPathRuntime(
        store=object(),  # type: ignore[arg-type]
        peer_base_url="https://peer.example",
        model_id="gemini-3.7-flash",
    )


def test_tool_surface_uses_batch_contact_instead_of_single_contact() -> None:
    names = [tool.__name__ for tool in runtime().tools()]
    assert "contact_candidates" in names
    assert "contact_candidate" not in names


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
