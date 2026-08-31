"""One bounded ADK/Gemini turn for an arbitrary user-owned Personal Agent."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from google import genai
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.runners import Runner
from pydantic import BaseModel, ConfigDict, Field

from pairpilot_orchestrator.config import Settings
from pairpilot_orchestrator.firestore_session_service import FirestoreSessionService
from pairpilot_orchestrator.multi_user_platform import MultiUserStore, stable_id

PUBLIC_AGENT_POST_FIELDS = {
    "schema_version",
    "intent_id",
    "owner_agent_id",
    "public_display_name",
    "task_type",
    "public_title",
    "public_summary",
    "public_constraints",
    "public_requirements",
    "status",
    "capacity_remaining",
    "authorship",
    "published_at",
    "expires_at",
}


def public_agent_projection(post: dict[str, Any]) -> dict[str, Any]:
    """Return the reviewed public fields that a peer Agent may inspect."""

    return {
        key: value for key, value in post.items() if key in PUBLIC_AGENT_POST_FIELDS
    }


def _policy_projection(runtime: dict[str, Any]) -> dict[str, Any]:
    privacy = dict(runtime.get("privacy", {}))
    autonomy = dict(runtime.get("autonomy", {}))
    return {
        "privacy": {
            key: privacy[key]
            for key in ("public_sharing_policy", "agent_sharing_policy")
            if key in privacy
        },
        "autonomy": {
            key: autonomy[key]
            for key in ("default_mode", "always_ask_policy")
            if key in autonomy
        },
    }


class BoundedNegotiationDecision(BaseModel):
    """Observable result only; no chain-of-thought or hidden confidence."""

    model_config = ConfigDict(extra="forbid")

    accepts_current_public_overlap: bool
    message_to_peer_agent: str = Field(min_length=1, max_length=500)
    public_reasons: list[str] = Field(default_factory=list, max_length=5)
    unresolved_public_questions: list[str] = Field(default_factory=list, max_length=5)


def _agent(settings: Settings) -> Agent:
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
        name="user_owned_personal_agent_negotiator",
        model=model,
        description="A generic user-owned PairPilot Personal Agent.",
        instruction=(
            "Act only for the supplied owner and task. Compare the two public intent "
            "projections under the supplied privacy and autonomy policies. Never infer "
            "identity, safety, or private facts. Never make a booking, payment, or "
            "final "
            "human commitment. Accept only a reversible proposal for introduction and "
            "coordination when event, location, and dates overlap. Your peer message "
            "must use only fields present in the public projections. Return only the "
            "structured BoundedNegotiationDecision."
        ),
        output_schema=BoundedNegotiationDecision,
        generate_content_config=genai.types.GenerateContentConfig(
            max_output_tokens=512,
            thinking_config=genai.types.ThinkingConfig(
                thinking_level=genai.types.ThinkingLevel.LOW
            ),
        ),
    )


async def run_personal_agent_turn(
    *,
    store: MultiUserStore,
    runtime: dict[str, Any],
    own_public_post: dict[str, Any],
    peer_public_post: dict[str, Any],
) -> BoundedNegotiationDecision:
    settings = Settings.from_environment()
    owner_uid = str(dict(runtime["owner"])["uid"])
    agent_id = str(dict(runtime["agent"])["agent_id"])
    own_intent_id = str(own_public_post["intent_id"])
    peer_intent_id = str(peer_public_post["intent_id"])
    session_id = stable_id("a2a_adk_session", agent_id, own_intent_id, peer_intent_id)
    invocation_id = f"a2a_invocation_{uuid4().hex}"
    started_at = datetime.now(UTC)
    started_clock = time.monotonic()
    sessions = FirestoreSessionService(store)
    existing = await sessions.get_session(
        app_name="pairpilot_multi_user_negotiation",
        user_id=owner_uid,
        session_id=session_id,
    )
    if existing is None:
        await sessions.create_session(
            app_name="pairpilot_multi_user_negotiation",
            user_id=owner_uid,
            session_id=session_id,
            state={
                "owner_agent_id": agent_id,
                "own_intent_id": own_intent_id,
                "peer_intent_id": peer_intent_id,
            },
        )
    runner = Runner(
        app_name="pairpilot_multi_user_negotiation",
        agent=_agent(settings),
        session_service=sessions,
    )
    policies = _policy_projection(runtime)
    prompt = {
        "actingAgentId": dict(runtime["agent"])["agent_id"],
        "ownPublicPost": public_agent_projection(own_public_post),
        "peerPublicPost": public_agent_projection(peer_public_post),
        "privacyPolicy": policies["privacy"],
        "autonomyPolicy": policies["autonomy"],
        "authority": {
            "mayNegotiateReversibleIntroduction": True,
            "mayCommitHuman": False,
            "mayDisclosePrivateMemory": False,
        },
    }
    fragments: list[str] = []
    input_tokens: int | None = None
    output_tokens: int | None = None
    turn_id = stable_id("a2a_turn", session_id, invocation_id)
    try:
        async for event in runner.run_async(
            user_id=owner_uid,
            session_id=session_id,
            invocation_id=invocation_id,
            new_message=genai.types.Content(
                role="user",
                parts=[genai.types.Part(text=json.dumps(prompt, default=str))],
            ),
        ):
            if event.usage_metadata:
                prompt_count = getattr(event.usage_metadata, "prompt_token_count", None)
                candidate_count = getattr(
                    event.usage_metadata, "candidates_token_count", None
                )
                if prompt_count is not None:
                    input_tokens = max(input_tokens or 0, prompt_count)
                if candidate_count is not None:
                    output_tokens = max(output_tokens or 0, candidate_count)
            if event.content:
                fragments.extend(
                    part.text for part in event.content.parts or [] if part.text
                )
        decision = BoundedNegotiationDecision.model_validate_json(
            "".join(fragments).strip()
        )
        await store.upsert(
            "a2a_agent_turns",
            turn_id,
            {
                "namespace": "production",
                "turn_id": turn_id,
                "owner_uid": owner_uid,
                "owner_agent_id": agent_id,
                "own_intent_id": own_intent_id,
                "peer_intent_id": peer_intent_id,
                "adk_session_id": session_id,
                "adk_invocation_id": invocation_id,
                "model_id": settings.model_id,
                "execution_mode": settings.execution_mode,
                "status": "COMPLETED",
                "started_at": started_at,
                "completed_at": datetime.now(UTC),
                "latency_ms": int((time.monotonic() - started_clock) * 1000),
                "input_token_count": input_tokens,
                "output_token_count": output_tokens,
                "observable_result": decision.model_dump(),
            },
        )
        return decision
    except Exception as exc:
        await store.upsert(
            "a2a_agent_turns",
            turn_id,
            {
                "namespace": "production",
                "turn_id": turn_id,
                "owner_uid": owner_uid,
                "owner_agent_id": agent_id,
                "own_intent_id": own_intent_id,
                "peer_intent_id": peer_intent_id,
                "adk_session_id": session_id,
                "adk_invocation_id": invocation_id,
                "model_id": settings.model_id,
                "execution_mode": settings.execution_mode,
                "status": "FAILED",
                "started_at": started_at,
                "completed_at": datetime.now(UTC),
                "latency_ms": int((time.monotonic() - started_clock) * 1000),
                "error_status": type(exc).__name__,
            },
        )
        raise


async def negotiate_pair_with_adk(
    *,
    store: MultiUserStore,
    source_runtime: dict[str, Any],
    target_runtime: dict[str, Any],
    source_post: dict[str, Any],
    target_post: dict[str, Any],
) -> dict[str, str]:
    """Run both independent Personal Agents; require both reversible acceptances."""

    source_decision, target_decision = await asyncio.gather(
        run_personal_agent_turn(
            store=store,
            runtime=source_runtime,
            own_public_post=source_post,
            peer_public_post=target_post,
        ),
        run_personal_agent_turn(
            store=store,
            runtime=target_runtime,
            own_public_post=target_post,
            peer_public_post=source_post,
        ),
    )
    if not (
        source_decision.accepts_current_public_overlap
        and target_decision.accepts_current_public_overlap
    ):
        raise ValueError("one Personal Agent declined the current public overlap")
    return {
        str(dict(source_runtime["agent"])["agent_id"]): (
            source_decision.message_to_peer_agent
        ),
        str(dict(target_runtime["agent"])["agent_id"]): (
            target_decision.message_to_peer_agent
        ),
    }
