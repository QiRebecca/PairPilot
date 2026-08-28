"""Qi Agent turns one user need into a reviewable, privacy-aware post draft."""

from google import genai
from google.adk.agents import Agent
from google.adk.models import Gemini
from pairpilot_schemas import IntentDraft

from pairpilot_orchestrator.config import Settings


def build_qi_intent_drafter_agent(settings: Settings) -> Agent:
    """Build the live structured drafting agent without publication authority."""

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
        name="qi_intent_drafter",
        model=model,
        description="Qi's personal agent for interpreting an owner-authored need.",
        instruction=(
            "Interpret only the user's ICML hotel-roommate request into the exact "
            "IntentDraft schema. This is a draft, never a publication or commitment. "
            "Keep public copy minimal. Put quiet compatibility, partial-date "
            "permission, and maximum extra cost in agent_only, not public_summary. "
            "Never repeat or invent protected sleep facts. Mark each core field as "
            "explicit_user_input only when the user actually stated it; otherwise use "
            "agent_inference and list the uncertainty. In this synthetic ICML demo, "
            "an unqualified July 6–10 means 2026; mark that year as agent_inference "
            "when it was not explicit. Do not turn an inference into "
            "an explicit fact. Return only the structured output."
        ),
        output_schema=IntentDraft,
        generate_content_config=genai.types.GenerateContentConfig(
            max_output_tokens=768,
            thinking_config=genai.types.ThinkingConfig(
                thinking_level=genai.types.ThinkingLevel.LOW
            ),
        ),
    )
