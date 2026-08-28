"""Live local A2A 1.x exchange; excluded from ordinary unit-test runs."""

from uuid import uuid4

import httpx
import pytest
from a2a.client import ClientConfig, create_client
from a2a.helpers.proto_helpers import get_message_text
from a2a.types import Message, Part, Role, SendMessageRequest
from pairpilot_peer_agents.a2a_server import create_app
from pairpilot_schemas import A2AMessageEnvelope, SpeechAct, canonical_intent_pair


@pytest.mark.asyncio
async def test_qi_reads_card_and_sends_live_a2a_message() -> None:
    app = create_app(
        base_url="http://testserver",
        project_id="pairpilot-agentic-ecb84a",
        model_id="gemini-3.7-flash",
        location="global",
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as http_client:
        client = await create_client(
            "http://testserver",
            client_config=ClientConfig(
                streaming=False,
                httpx_client=http_client,
                supported_protocol_bindings=["JSONRPC"],
            ),
        )
        source_intent_id = "intent_qi_icml_roommate"
        envelope = A2AMessageEnvelope(
            run_id=uuid4(),
            session_id=uuid4(),
            from_agent_id="qi-agent",
            to_agent_id="alice-agent",
            from_intent_id=source_intent_id,
            to_intent_id=source_intent_id,
            pair_session_id=canonical_intent_pair(source_intent_id, source_intent_id),
            speech_act=SpeechAct.INTRODUCTION_REQUEST,
            natural_language=(
                "My user seeks a verified female ICML roommate in Seoul for "
                "July 6-10. Quiet overnight compatibility is the top priority. "
                "Could you decide whether a relevant warm introduction is appropriate?"
            ),
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

    assert len(responses) == 1
    assert responses[0].HasField("message")
    outbound = A2AMessageEnvelope.model_validate_json(
        get_message_text(responses[0].message)
    )
    decision_claim = next(
        claim for claim in outbound.claims if claim.field == "introduction_decision"
    )
    assert decision_claim.value in {
        "OFFER_INTRODUCTION",
        "DECLINE_INTRODUCTION",
    }
    assert outbound.from_agent_id == "alice-agent"
    assert outbound.to_agent_id == "qi-agent"
    assert outbound.speech_act == SpeechAct.INTRODUCTION_RESPONSE
    introduced_agents = [
        claim for claim in outbound.claims if claim.field == "introduced_agent_id"
    ]
    introduced_intents = [
        claim for claim in outbound.claims if claim.field == "introduced_intent_id"
    ]
    assert len(introduced_agents) == len(introduced_intents)
    assert app.state.agent_card.supported_interfaces[0].protocol_version == "1.0"
    assert len(app.state.provenance_store.records) == 1
    provenance = app.state.provenance_store.records[0]
    assert provenance.inbound_message_id == str(envelope.message_id)
    assert provenance.exact_model_id == "gemini-3.7-flash"
    for handler in app.state.a2a_handlers.values():
        await handler.aclose()
