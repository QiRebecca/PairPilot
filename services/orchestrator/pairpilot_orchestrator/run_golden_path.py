"""Run the live CLI golden path until a safe terminal or approval boundary."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import UUID

from google import genai
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from pairpilot_orchestrator.agents import build_qi_coordinator_agent
from pairpilot_orchestrator.config import Settings
from pairpilot_orchestrator.infrastructure import GoogleCloudStore
from pairpilot_orchestrator.workflow import GoldenPathRuntime

GOAL_TEXT = """Find me a female roommate for ICML in Seoul from July 6 to July 10.
A quiet overnight environment matters more than getting the lowest price.
I can accept partial date overlap if the additional cost stays below $70."""


async def run(*, run_id: UUID | None = None) -> dict[str, Any]:
    """Execute bounded live ADK coordination and return observable evidence."""

    settings = Settings.from_environment()
    peer_base_url = os.environ["PAIRPILOT_PEER_BASE_URL"]
    store = GoogleCloudStore(project_id=settings.project_id)
    runtime = GoldenPathRuntime(
        store=store,
        peer_base_url=peer_base_url,
        model_id=settings.model_id,
        run_id=run_id,
    )
    await runtime.initialize(GOAL_TEXT)
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="pairpilot_qi_coordinator",
        user_id="qi-owner",
        session_id=str(runtime.session_id),
    )
    runner = Runner(
        app_name="pairpilot_qi_coordinator",
        agent=build_qi_coordinator_agent(settings, runtime=runtime),
        session_service=session_service,
    )
    user_message = genai.types.Content(
        role="user", parts=[genai.types.Part(text=GOAL_TEXT)]
    )
    tool_calls: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    observable_texts: list[str] = []
    token_usage: list[dict[str, Any]] = []
    model_retry_count = 0
    started = perf_counter()
    error: str | None = None
    try:
        async with asyncio.timeout(90):
            next_message = user_message
            while True:
                try:
                    async for event in runner.run_async(
                        user_id="qi-owner",
                        session_id=str(runtime.session_id),
                        new_message=next_message,
                    ):
                        if event.usage_metadata:
                            token_usage.append(
                                event.usage_metadata.model_dump(mode="json")
                            )
                            if len(token_usage) > runtime.MAX_AGENT_TURNS:
                                raise RuntimeError("maximum global agent turns reached")
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
                                            "response": dict(
                                                part.function_response.response or {}
                                            ),
                                        }
                                    )
                                if part.text:
                                    observable_texts.append(part.text)
                    break
                except Exception as exc:
                    if model_retry_count >= 2 or "429" not in str(exc):
                        raise
                    model_retry_count += 1
                    await asyncio.sleep(4 * model_retry_count)
                    next_message = (
                        user_message
                        if runtime.tool_count == 0
                        else genai.types.Content(
                            role="user",
                            parts=[
                                genai.types.Part(
                                    text=(
                                        "Continue the same active goal from the "
                                        "current session and persisted tool results. "
                                        "Do not repeat successful actions."
                                    )
                                )
                            ],
                        )
                    )
    except TimeoutError:
        if runtime.status != "WAITING_FOR_HUMAN_APPROVAL":
            runtime.status = "TIMEOUT"
            error = "maximum wall-clock time reached"
    except Exception as exc:
        runtime.status = "FAILED_SAFE"
        error = f"{type(exc).__name__}: {exc}"

    if runtime.status == "RUNNING":
        runtime.status = "NO_PROGRESS"
        error = error or "model turn ended without a terminal action"
    if runtime.status in {"TIMEOUT", "FAILED_SAFE", "NO_PROGRESS"}:
        await store.upsert(
            "runs",
            str(runtime.run_id),
            {
                "runId": str(runtime.run_id),
                "goalId": str(runtime.goal_id),
                "sessionId": str(runtime.session_id),
                "status": runtime.status,
                "terminationReason": error,
                "exactModelId": settings.model_id,
                "executionMode": settings.execution_mode,
                "updatedAt": datetime.now(UTC),
            },
        )
        await store.write_event(
            event_type="run.failed",
            run_id=str(runtime.run_id),
            producer="orchestrator",
            payload={"status": runtime.status, "reason": error or "unknown"},
            idempotency_key=f"{runtime.run_id}:run.failed:{runtime.status}",
        )

    elapsed_ms = int((perf_counter() - started) * 1000)
    flushed_outbox_events = await store.flush_pending_events(run_id=str(runtime.run_id))
    result = {
        "run_id": str(runtime.run_id),
        "goal_id": str(runtime.goal_id),
        "session_id": str(runtime.session_id),
        "status": runtime.status,
        "execution_mode": settings.execution_mode,
        "exact_model_id": settings.model_id,
        "tool_count": runtime.tool_count,
        "model_retry_count": model_retry_count,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "observable_texts": observable_texts,
        "effect_contract": runtime.effect_contract,
        "token_usage_events": token_usage,
        "latency_ms": elapsed_ms,
        "latency_to_boundary_ms": runtime.boundary_elapsed_ms,
        "flushed_outbox_events": flushed_outbox_events,
        "error": error,
    }
    await store.upsert("run_outputs", str(runtime.run_id), result)
    return result


def main() -> None:
    print(json.dumps(asyncio.run(run()), indent=2))


if __name__ == "__main__":
    main()
