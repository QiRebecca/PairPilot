"""Run a live Qi ADK turn whose model-selected tool performs remote A2A."""

import asyncio
import json
import os

from google import genai
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from pairpilot_orchestrator.agents import build_qi_a2a_spike_agent
from pairpilot_orchestrator.config import Settings


async def run() -> dict[str, object]:
    """Execute the Cloud Run A2A spike and return observable evidence."""

    settings = Settings.from_environment()
    peer_base_url = os.environ["PAIRPILOT_PEER_BASE_URL"]
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="pairpilot_qi_a2a_spike",
        user_id="qi-owner",
        session_id="qi-a2a-live-001",
    )
    runner = Runner(
        app_name="pairpilot_qi_a2a_spike",
        agent=build_qi_a2a_spike_agent(
            settings, peer_base_url=peer_base_url
        ),
        session_service=session_service,
    )
    tool_calls: list[dict[str, object]] = []
    tool_results: list[dict[str, object]] = []
    texts: list[str] = []
    message = genai.types.Content(
        role="user",
        parts=[
            genai.types.Part(
                text=(
                    "Find a relationship-aware path to a verified female ICML "
                    "roommate for Seoul, July 6-10. Quiet overnight compatibility "
                    "is the dominant preference. Use minimum-necessary disclosure."
                )
            )
        ],
    )
    async for event in runner.run_async(
        user_id="qi-owner",
        session_id="qi-a2a-live-001",
        new_message=message,
    ):
        if event.content:
            for part in event.content.parts or []:
                if part.function_call:
                    tool_calls.append(
                        {
                            "name": part.function_call.name,
                            "args": dict(part.function_call.args or {}),
                        }
                    )
                if part.function_response:
                    tool_results.append(
                        {
                            "name": part.function_response.name,
                            "response": dict(part.function_response.response or {}),
                        }
                    )
                if part.text:
                    texts.append(part.text)

    if [call["name"] for call in tool_calls] != ["request_warm_introduction"]:
        raise RuntimeError("Qi did not select the remote A2A tool exactly once")
    return {
        "mode": settings.execution_mode,
        "model": settings.model_id,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "texts": texts,
    }


def main() -> None:
    print(json.dumps(asyncio.run(run()), indent=2))


if __name__ == "__main__":
    main()

