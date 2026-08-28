"""Run the live Qi drafting agent and validate its structured result."""

from uuid import uuid4

from google import genai
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from pairpilot_schemas import IntentDraft

from pairpilot_orchestrator.agents.qi_intent_drafter import (
    build_qi_intent_drafter_agent,
)
from pairpilot_orchestrator.config import Settings


async def draft_with_qi_agent(raw_goal: str) -> IntentDraft:
    """Interpret one raw owner input through live ADK/Gemini structured output."""

    settings = Settings.from_environment()
    session_id = str(uuid4())
    sessions = InMemorySessionService()
    await sessions.create_session(
        app_name="pairpilot_intent_drafting",
        user_id="qi-owner",
        session_id=session_id,
    )
    runner = Runner(
        app_name="pairpilot_intent_drafting",
        agent=build_qi_intent_drafter_agent(settings),
        session_service=sessions,
    )
    fragments: list[str] = []
    async for event in runner.run_async(
        user_id="qi-owner",
        session_id=session_id,
        new_message=genai.types.Content(
            role="user", parts=[genai.types.Part(text=raw_goal)]
        ),
    ):
        if event.content:
            fragments.extend(
                part.text for part in event.content.parts or [] if part.text
            )
    return IntentDraft.model_validate_json("".join(fragments).strip())
