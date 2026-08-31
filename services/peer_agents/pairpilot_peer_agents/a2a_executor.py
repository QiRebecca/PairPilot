"""Official A2A 1.x executor adapting requests to isolated peer ADK sessions."""

from collections.abc import Callable
from datetime import UTC, datetime

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Message, Part, Role
from google import genai
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from pairpilot_schemas import (
    A2AMessageEnvelope,
    Claim,
    ClaimSource,
    PeerDecision,
)
from pydantic import ValidationError

from pairpilot_peer_agents.provenance import ProvenanceStore

AgentBuilder = Callable[..., Agent]


class PeerAgentExecutor(AgentExecutor):
    """Run one named peer using an isolated runner, context, and session store."""

    MAX_MODEL_ATTEMPTS = 3

    def __init__(
        self,
        *,
        agent_id: str,
        owner_id: str,
        agent_builder: AgentBuilder,
        project_id: str,
        model_id: str,
        location: str,
        provenance_store: ProvenanceStore,
    ) -> None:
        self.agent_id = agent_id
        self.owner_id = owner_id
        self._model_id = model_id
        self._provenance_store = provenance_store
        self._app_name = f"pairpilot_{agent_id.replace('-', '_')}"
        self._session_service = InMemorySessionService()
        self._runner = Runner(
            app_name=self._app_name,
            agent=agent_builder(
                project_id=project_id,
                model_id=model_id,
                location=location,
            ),
            session_service=self._session_service,
        )

    async def _ensure_session(self, session_id: str) -> None:
        existing = await self._session_service.get_session(
            app_name=self._app_name,
            user_id=self.owner_id,
            session_id=session_id,
        )
        if existing is None:
            await self._session_service.create_session(
                app_name=self._app_name,
                user_id=self.owner_id,
                session_id=session_id,
            )

    def _validate_decision(self, decision: PeerDecision) -> None:
        if self.agent_id == "alice-agent":
            if decision.action not in {
                "OFFER_INTRODUCTION",
                "DECLINE_INTRODUCTION",
            }:
                raise ValueError("Alice returned an unauthorized decision type")
        elif decision.action in {
            "OFFER_INTRODUCTION",
            "DECLINE_INTRODUCTION",
        }:
            raise ValueError("roommate candidate returned introduction authority")

    async def _generate_decision(
        self, *, session_id: str, user_message: genai.types.Content
    ) -> tuple[PeerDecision, bool]:
        """Retry invalid output, then return an explicit nonresponse decision."""

        next_message = user_message
        last_error: ValidationError | None = None
        for attempt in range(self.MAX_MODEL_ATTEMPTS):
            response_fragments: list[str] = []
            async for event in self._runner.run_async(
                user_id=self.owner_id,
                session_id=session_id,
                new_message=next_message,
            ):
                if event.content:
                    response_fragments.extend(
                        part.text for part in event.content.parts or [] if part.text
                    )
            try:
                return (
                    PeerDecision.model_validate_json(
                        "".join(response_fragments).strip()
                    ),
                    True,
                )
            except ValidationError as exc:
                last_error = exc
                if attempt + 1 == self.MAX_MODEL_ATTEMPTS:
                    break
                next_message = genai.types.Content(
                    role="user",
                    parts=[
                        genai.types.Part(
                            text=(
                                "Your prior turn was empty or did not satisfy the "
                                "required PeerDecision schema. Re-evaluate the same "
                                "request and return only a complete structured "
                                "PeerDecision. Do not change authority or invent facts."
                            )
                        )
                    ],
                )
        assert last_error is not None
        if self.agent_id == "alice-agent":
            return (
                PeerDecision(
                    action="DECLINE_INTRODUCTION",
                    speech_act="INTRODUCTION_RESPONSE",
                    natural_language=(
                        "This Agent could not produce a valid response after "
                        "bounded retries. No introduction or compatibility is implied."
                    ),
                    claims=[],
                    reason="MODEL_NO_VALID_OUTPUT_AFTER_BOUNDED_RETRIES",
                    confidence=0.0,
                ),
                False,
            )
        return (
            PeerDecision(
                action="PROVIDE_INFORMATION",
                speech_act="INFORMATION_RESPONSE",
                natural_language=(
                    "This Agent could not produce a valid response after bounded "
                    "retries. No compatibility, fact, or acceptance is implied."
                ),
                claims=[],
                reason="MODEL_NO_VALID_OUTPUT_AFTER_BOUNDED_RETRIES",
                confidence=0.0,
            ),
            False,
        )

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        inbound = context.message
        if inbound is None:
            raise ValueError("A2A request is missing a message")
        envelope = A2AMessageEnvelope.model_validate_json(context.get_user_input())
        if envelope.to_agent_id != self.agent_id:
            raise ValueError("A2A envelope addressed to a different agent")
        if envelope.expires_at and envelope.expires_at <= datetime.now(UTC):
            raise ValueError("A2A envelope expired")

        session_id = str(envelope.session_id)
        await self._ensure_session(session_id)
        user_message = genai.types.Content(
            role="user",
            parts=[genai.types.Part(text=envelope.model_dump_json())],
        )

        decision, live_model_output = await self._generate_decision(
            session_id=session_id, user_message=user_message
        )
        self._validate_decision(decision)
        claims = [
            Claim(
                field=item.field,
                value=item.value,
                source=ClaimSource.PEER_AGENT_REPORT,
                confidence=item.confidence,
            )
            for item in decision.claims
            if not (
                self.agent_id == "alice-agent"
                and item.field
                in {
                    "introduction_decision",
                    "introduced_agent_id",
                    "introduced_intent_id",
                }
            )
        ]
        if self.agent_id == "alice-agent":
            claims.append(
                Claim(
                    field="introduction_decision",
                    value=decision.action,
                    source=ClaimSource.PEER_AGENT_REPORT,
                    confidence=decision.confidence,
                )
            )
            if (
                decision.action == "OFFER_INTRODUCTION"
                and decision.introduced_agent_id is not None
            ):
                claims.append(
                    Claim(
                        field="introduced_agent_id",
                        value=decision.introduced_agent_id,
                        source=ClaimSource.PEER_AGENT_REPORT,
                        confidence=decision.confidence,
                    )
                )
            if (
                decision.action == "OFFER_INTRODUCTION"
                and decision.introduced_intent_id is not None
            ):
                claims.append(
                    Claim(
                        field="introduced_intent_id",
                        value=decision.introduced_intent_id,
                        source=ClaimSource.PEER_AGENT_REPORT,
                        confidence=decision.confidence,
                    )
                )
        if decision.accepted_proposal_version is not None and not any(
            item.field == "proposal_version" for item in claims
        ):
            claims.append(
                Claim(
                    field="proposal_version",
                    value=decision.accepted_proposal_version,
                    source=ClaimSource.PEER_AGENT_REPORT,
                    confidence=decision.confidence,
                )
            )
        outbound = A2AMessageEnvelope(
            run_id=envelope.run_id,
            session_id=envelope.session_id,
            from_agent_id=self.agent_id,
            to_agent_id=envelope.from_agent_id,
            from_intent_id=(
                decision.introduced_intent_id
                if self.agent_id == "alice-agent"
                and decision.action == "OFFER_INTRODUCTION"
                and decision.introduced_intent_id is not None
                else envelope.to_intent_id
            ),
            to_intent_id=envelope.from_intent_id,
            pair_session_id=envelope.pair_session_id,
            speech_act=decision.speech_act,
            natural_language=decision.natural_language,
            claims=claims,
            proposal=(
                envelope.proposal if decision.action == "ACCEPT_PROPOSAL" else None
            ),
        )
        response_text = outbound.model_dump_json()
        await self._provenance_store.persist(
            inbound_message_id=inbound.message_id,
            outbound_message_id=str(outbound.message_id),
            response_text=response_text,
            model_id=(
                self._model_id
                if live_model_output
                else "SYSTEM_BOUNDED_NONRESPONSE"
            ),
        )
        await event_queue.enqueue_event(
            Message(
                message_id=str(outbound.message_id),
                task_id=context.task_id,
                context_id=context.context_id,
                role=Role.ROLE_AGENT,
                parts=[Part(text=response_text)],
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("Immediate peer decisions cannot be canceled")
