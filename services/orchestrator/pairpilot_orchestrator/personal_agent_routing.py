"""Run the persistent Qi Agent against bounded task summaries."""

import json
from collections.abc import Sequence
from uuid import uuid4

from google import genai
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from pairpilot_schemas import PersonalAgentRoutingResult

from pairpilot_orchestrator.agents.qi_personal_router import (
    build_qi_personal_router_agent,
)
from pairpilot_orchestrator.config import Settings


async def route_personal_agent_message(
    *,
    message: str,
    task_summaries: Sequence[dict[str, object]],
    current_task_id: str | None,
) -> PersonalAgentRoutingResult:
    """Classify one message without loading unrelated private transcripts."""

    settings = Settings.from_environment()
    session_id = str(uuid4())
    sessions = InMemorySessionService()
    await sessions.create_session(
        app_name="pairpilot_personal_agent",
        user_id="qi-owner",
        session_id=session_id,
    )
    runner = Runner(
        app_name="pairpilot_personal_agent",
        agent=build_qi_personal_router_agent(settings),
        session_service=sessions,
    )
    prompt = json.dumps(
        {
            "current_task_id": current_task_id,
            "task_summaries": list(task_summaries),
            "user_message": message,
        },
        separators=(",", ":"),
        default=str,
    )
    fragments: list[str] = []
    async for event in runner.run_async(
        user_id="qi-owner",
        session_id=session_id,
        new_message=genai.types.Content(
            role="user", parts=[genai.types.Part(text=prompt)]
        ),
    ):
        if event.content:
            fragments.extend(
                part.text for part in event.content.parts or [] if part.text
            )
    return PersonalAgentRoutingResult.model_validate_json("".join(fragments).strip())
