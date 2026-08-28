"""Run the authenticated minimal Google ADK verification turn."""

import asyncio
import json

from google import genai
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from pairpilot_orchestrator.agents import build_qi_spike_agent
from pairpilot_orchestrator.config import Settings


async def run() -> dict[str, object]:
    """Execute one live bounded agent turn and return observable evidence."""

    settings = Settings.from_environment()
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="pairpilot_adk_spike",
        user_id="verification-user",
        session_id="adk-live-001",
    )
    runner = Runner(
        app_name="pairpilot_adk_spike",
        agent=build_qi_spike_agent(settings),
        session_service=session_service,
    )

    tool_calls: list[dict[str, object]] = []
    texts: list[str] = []
    usage: list[dict[str, object]] = []
    message = genai.types.Content(
        role="user",
        parts=[genai.types.Part(text="Verify the PairPilot Qi agent runtime now.")],
    )
    async for event in runner.run_async(
        user_id="verification-user",
        session_id="adk-live-001",
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
                if part.text:
                    texts.append(part.text)
        if event.usage_metadata:
            usage.append(event.usage_metadata.model_dump(exclude_none=True))

    if [call["name"] for call in tool_calls] != ["verify_runtime_identity"]:
        raise RuntimeError("Live Gemini did not select the required ADK tool once")

    return {
        "model": settings.model_id,
        "mode": settings.execution_mode,
        "tool_calls": tool_calls,
        "texts": texts,
        "usage": usage,
    }


def main() -> None:
    """CLI entry point."""

    print(json.dumps(asyncio.run(run()), indent=2))


if __name__ == "__main__":
    main()
