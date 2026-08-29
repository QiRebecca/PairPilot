"""One bounded ADK/Gemini turn for an arbitrary user-owned Personal Agent."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import uuid4

from google import genai
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from pydantic import BaseModel, ConfigDict, Field

from pairpilot_orchestrator.config import Settings

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
    runtime: dict[str, Any],
    own_public_post: dict[str, Any],
    peer_public_post: dict[str, Any],
) -> BoundedNegotiationDecision:
    settings = Settings.from_environment()
    session_id = str(uuid4())
    owner_uid = str(dict(runtime["owner"])["uid"])
    sessions = InMemorySessionService()
    await sessions.create_session(
        app_name="pairpilot_multi_user_negotiation",
        user_id=owner_uid,
        session_id=session_id,
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
    async for event in runner.run_async(
        user_id=owner_uid,
        session_id=session_id,
        new_message=genai.types.Content(
            role="user",
            parts=[genai.types.Part(text=json.dumps(prompt, default=str))],
        ),
    ):
        if event.content:
            fragments.extend(
                part.text for part in event.content.parts or [] if part.text
            )
    return BoundedNegotiationDecision.model_validate_json("".join(fragments).strip())


async def negotiate_pair_with_adk(
    *,
    source_runtime: dict[str, Any],
    target_runtime: dict[str, Any],
    source_post: dict[str, Any],
    target_post: dict[str, Any],
) -> dict[str, str]:
    """Run both independent Personal Agents; require both reversible acceptances."""

    source_decision, target_decision = await asyncio.gather(
        run_personal_agent_turn(
            runtime=source_runtime,
            own_public_post=source_post,
            peer_public_post=target_post,
        ),
        run_personal_agent_turn(
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
