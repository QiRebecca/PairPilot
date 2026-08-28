"""Typed A2A 1.x client used by model-selected Qi Agent tools."""

import asyncio
import os
from uuid import UUID, uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers.proto_helpers import get_message_text
from a2a.types import Message, Part, Role, SendMessageRequest
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from pairpilot_schemas import (
    A2AMessageEnvelope,
    A2AProposal,
    IntroductionDecision,
    SpeechAct,
)
from pydantic import BaseModel, ConfigDict


class A2AExchangeResult(BaseModel):
    """Observable non-secret result returned to Qi Agent."""

    model_config = ConfigDict(extra="forbid")

    agent_card_name: str
    agent_card_version: str
    protocol: str
    inbound_message_id: str
    outbound_message_id: str
    decision: IntroductionDecision


class PeerA2AExchangeResult(BaseModel):
    """Validated result from any logically independent peer agent."""

    model_config = ConfigDict(extra="forbid")

    agent_card_name: str
    agent_card_version: str
    protocol: str
    inbound_message_id: UUID
    outbound_message_id: UUID
    response: A2AMessageEnvelope


PEER_CARD_PATHS = {
    "alice-agent": "/.well-known/agents/alice-agent.json",
    "maya-agent": "/.well-known/agents/maya-agent.json",
    "lena-agent": "/.well-known/agents/lena-agent.json",
}


async def _identity_token(audience: str) -> str:
    """Get a short-lived ID token without creating service-account keys."""

    injected = os.environ.get("PAIRPILOT_PEER_ID_TOKEN", "")
    if injected:
        return injected
    return await asyncio.to_thread(id_token.fetch_id_token, Request(), audience)


async def request_alice_introduction(
    *, peer_base_url: str, request_summary: str
) -> dict[str, object]:
    """Resolve Alice's Agent Card and send a validated A2A v1 message."""

    result = await request_peer_agent(
        peer_base_url=peer_base_url,
        to_agent_id="alice-agent",
        speech_act=SpeechAct.INTRODUCTION_REQUEST,
        natural_language=request_summary,
    )
    outbound = result.response
    decision_claim = next(
        (claim for claim in outbound.claims if claim.field == "introduction_decision"),
        None,
    )
    if decision_claim is None or decision_claim.value not in {
        "OFFER_INTRODUCTION",
        "DECLINE_INTRODUCTION",
    }:
        raise RuntimeError("Alice response omitted its introduction decision claim")
    decision = IntroductionDecision(
        decision=decision_claim.value,
        natural_language=outbound.natural_language,
        reason="Independent decision returned through Alice's validated A2A envelope.",
        confidence=decision_claim.confidence,
    )
    return A2AExchangeResult(
        agent_card_name=result.agent_card_name,
        agent_card_version=result.agent_card_version,
        protocol=result.protocol,
        inbound_message_id=str(result.inbound_message_id),
        outbound_message_id=str(result.outbound_message_id),
        decision=decision,
    ).model_dump(mode="json")


async def request_peer_agent(
    *,
    peer_base_url: str,
    to_agent_id: str,
    speech_act: SpeechAct,
    natural_language: str,
    run_id: UUID | None = None,
    session_id: UUID | None = None,
    proposal: A2AProposal | None = None,
) -> PeerA2AExchangeResult:
    """Resolve a named peer card and send one validated A2A v1 envelope."""

    card_path = PEER_CARD_PATHS.get(to_agent_id)
    if card_path is None:
        raise ValueError("unknown peer agent")
    envelope = A2AMessageEnvelope(
        run_id=run_id or uuid4(),
        session_id=session_id or uuid4(),
        from_agent_id="qi-agent",
        to_agent_id=to_agent_id,
        speech_act=speech_act,
        natural_language=natural_language,
        proposal=proposal,
    )
    bearer_token = await _identity_token(peer_base_url)
    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {bearer_token}"}, timeout=60
    ) as http_client:
        card = await A2ACardResolver(http_client, peer_base_url).get_agent_card(
            relative_card_path=card_path
        )
        client = ClientFactory(
            ClientConfig(
                streaming=False,
                httpx_client=http_client,
                supported_protocol_bindings=["JSONRPC"],
            )
        ).create(card)
        request = SendMessageRequest(
            message=Message(
                message_id=str(envelope.message_id),
                role=Role.ROLE_USER,
                parts=[Part(text=envelope.model_dump_json())],
            )
        )
        responses = [response async for response in client.send_message(request)]
        await client.close()

    if len(responses) != 1 or not responses[0].HasField("message"):
        raise RuntimeError("peer A2A endpoint returned an invalid response stream")
    response = responses[0].message
    outbound = A2AMessageEnvelope.model_validate_json(get_message_text(response))
    if outbound.from_agent_id != to_agent_id or outbound.to_agent_id != "qi-agent":
        raise RuntimeError("peer returned a misrouted A2A envelope")
    return PeerA2AExchangeResult(
        agent_card_name=card.name,
        agent_card_version=card.version,
        protocol="A2A/JSON-RPC/1.0",
        inbound_message_id=envelope.message_id,
        outbound_message_id=UUID(response.message_id),
        response=outbound,
    )
