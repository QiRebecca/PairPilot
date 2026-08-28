"""Typed A2A 1.x client used by model-selected Qi Agent tools."""

import asyncio
import os
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers.proto_helpers import get_message_text
from a2a.types import Message, Part, Role, SendMessageRequest
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from pydantic import BaseModel, ConfigDict

from pairpilot_schemas import (
    A2AMessageEnvelope,
    IntroductionDecision,
    SpeechAct,
)


class A2AExchangeResult(BaseModel):
    """Observable non-secret result returned to Qi Agent."""

    model_config = ConfigDict(extra="forbid")

    agent_card_name: str
    agent_card_version: str
    protocol: str
    inbound_message_id: str
    outbound_message_id: str
    decision: IntroductionDecision


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

    envelope = A2AMessageEnvelope(
        run_id=uuid4(),
        session_id=uuid4(),
        from_agent_id="qi-agent",
        to_agent_id="alice-agent",
        speech_act=SpeechAct.INTRODUCTION_REQUEST,
        natural_language=request_summary,
    )
    bearer_token = await _identity_token(peer_base_url)
    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {bearer_token}"}, timeout=60
    ) as http_client:
        card = await A2ACardResolver(http_client, peer_base_url).get_agent_card()
        client = ClientFactory(
            ClientConfig(
                streaming=False,
                httpx_client=http_client,
                supported_protocol_bindings=["JSONRPC"],
            )
        ).create(
            card
        )
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
        raise RuntimeError("Alice A2A endpoint returned an invalid response stream")
    response = responses[0].message
    decision = IntroductionDecision.model_validate_json(
        get_message_text(response)
    )
    result = A2AExchangeResult(
        agent_card_name=card.name,
        agent_card_version=card.version,
        protocol="A2A/JSON-RPC/1.0",
        inbound_message_id=str(envelope.message_id),
        outbound_message_id=response.message_id,
        decision=decision,
    )
    return result.model_dump(mode="json")
