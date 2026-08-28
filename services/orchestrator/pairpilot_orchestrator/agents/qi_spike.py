"""Minimal live Qi Agent used to prove Google ADK tool selection."""

from google import genai
from google.adk.agents import Agent
from google.adk.models import Gemini

from pairpilot_orchestrator.config import Settings
from pairpilot_orchestrator.tools.runtime import verify_runtime_identity


def build_qi_spike_agent(settings: Settings) -> Agent:
    """Construct a live Vertex-authenticated Google ADK agent."""

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
        name="qi_agent_spike",
        model=model,
        description="Minimal live PairPilot Google ADK verification agent.",
        instruction=(
            "You are a runtime verifier. For every request, call "
            "verify_runtime_identity exactly once with component='qi-agent'. "
            "Then answer with only a concise confirmation derived from the tool "
            "result. Never invent a tool result."
        ),
        tools=[verify_runtime_identity],
        generate_content_config=genai.types.GenerateContentConfig(
            max_output_tokens=128,
            thinking_config=genai.types.ThinkingConfig(
                thinking_level=genai.types.ThinkingLevel.LOW
            ),
        ),
    )
