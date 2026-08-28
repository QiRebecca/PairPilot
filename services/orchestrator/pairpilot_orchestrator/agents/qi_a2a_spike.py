"""Qi Agent independently selects the remote warm-introduction action."""

from collections.abc import Callable, Coroutine
from typing import Any

from google import genai
from google.adk.agents import Agent
from google.adk.models import Gemini

from pairpilot_orchestrator.a2a_client import request_alice_introduction
from pairpilot_orchestrator.config import Settings


def build_qi_a2a_spike_agent(settings: Settings, *, peer_base_url: str) -> Agent:
    """Build Qi with a legitimate remote A2A tool and no route hardcoding."""

    async def request_warm_introduction(
        request_summary: str,
    ) -> dict[str, object]:
        """Ask Alice Agent to independently evaluate a warm introduction."""

        return await request_alice_introduction(
            peer_base_url=peer_base_url,
            request_summary=request_summary,
        )

    typed_tool: Callable[..., Coroutine[Any, Any, dict[str, object]]] = (
        request_warm_introduction
    )
    model = Gemini(
        model=settings.model_id,
        api_version="v1",
        client_kwargs={
            "enterprise": True,
            "project": settings.project_id,
            "location": settings.model_location,
        },
    )
    return Agent(
        name="qi_a2a_spike",
        model=model,
        description="Qi's live personal agent with an official remote A2A tool.",
        instruction=(
            "You are Qi Agent. Given a high-level coordination goal, decide whether "
            "the available warm-introduction tool is relevant. If it is, call "
            "request_warm_introduction exactly once with a minimum-necessary summary. "
            "Never include private personal facts. Base your concise answer only on "
            "the remote agent's structured response."
        ),
        tools=[typed_tool],
        generate_content_config=genai.types.GenerateContentConfig(
            max_output_tokens=256,
            thinking_config=genai.types.ThinkingConfig(
                thinking_level=genai.types.ThinkingLevel.LOW
            ),
        ),
    )
