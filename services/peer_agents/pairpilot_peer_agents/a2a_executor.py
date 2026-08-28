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

from pairpilot_peer_agents.provenance import ProvenanceStore

AgentBuilder = Callable[..., Agent]


class PeerAgentExecutor(AgentExecutor):
    """Run one named peer using an isolated runner, context, and session store."""

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

        response_fragments: list[str] = []
        async for event in self._runner.run_async(
            user_id=self.owner_id,
            session_id=session_id,
            new_message=user_message,
        ):
            if event.content:
                response_fragments.extend(
                    part.text for part in event.content.parts or [] if part.text
                )

        decision = PeerDecision.model_validate_json("".join(response_fragments).strip())
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
                and item.field in {"introduction_decision", "introduced_agent_id"}
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
            if decision.introduced_agent_id is not None:
                claims.append(
                    Claim(
                        field="introduced_agent_id",
                        value=decision.introduced_agent_id,
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
            model_id=self._model_id,
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
