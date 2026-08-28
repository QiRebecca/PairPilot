"""Official A2A 1.x executor adapting requests to Alice's ADK session."""

from uuid import uuid4

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import Message, Part, Role
from google import genai
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from pairpilot_peer_agents.agents import (
    IntroductionDecision,
    build_alice_agent,
)
from pairpilot_peer_agents.provenance import ProvenanceStore


class AliceAgentExecutor(AgentExecutor):
    """Execute each A2A request in Alice's isolated ADK session namespace."""

    def __init__(
        self,
        *,
        project_id: str,
        model_id: str,
        location: str,
        provenance_store: ProvenanceStore,
    ) -> None:
        self._model_id = model_id
        self._provenance_store = provenance_store
        self._session_service = InMemorySessionService()
        self._runner = Runner(
            app_name="pairpilot_alice_agent",
            agent=build_alice_agent(
                project_id=project_id,
                model_id=model_id,
                location=location,
            ),
            session_service=self._session_service,
        )

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        inbound = context.message
        if inbound is None:
            raise ValueError("A2A request is missing a message")

        session_id = context.context_id or str(uuid4())
        await self._session_service.create_session(
            app_name="pairpilot_alice_agent",
            user_id="alice-owner",
            session_id=session_id,
        )
        user_message = genai.types.Content(
            role="user",
            parts=[genai.types.Part(text=context.get_user_input())],
        )

        response_fragments: list[str] = []
        async for event in self._runner.run_async(
            user_id="alice-owner",
            session_id=session_id,
            new_message=user_message,
        ):
            if event.content:
                response_fragments.extend(
                    part.text
                    for part in event.content.parts or []
                    if part.text
                )

        decision_text = "".join(response_fragments).strip()
        decision = IntroductionDecision.model_validate_json(decision_text)
        outbound_id = str(uuid4())
        await self._provenance_store.persist(
            inbound_message_id=inbound.message_id,
            outbound_message_id=outbound_id,
            response_text=decision.model_dump_json(),
            model_id=self._model_id,
        )
        await event_queue.enqueue_event(
            Message(
                message_id=outbound_id,
                task_id=context.task_id,
                context_id=context.context_id,
                role=Role.ROLE_AGENT,
                parts=[Part(text=decision.model_dump_json())],
            )
        )

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        raise NotImplementedError("Immediate introduction decisions cannot be canceled")
