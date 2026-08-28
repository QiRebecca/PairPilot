"""Starlette service exposing Alice through official A2A 1.x routes."""

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from starlette.applications import Starlette

from pairpilot_peer_agents.a2a_executor import AliceAgentExecutor
from pairpilot_peer_agents.provenance import (
    FirestoreProvenanceStore,
    InMemoryProvenanceStore,
)


def build_alice_agent_card(base_url: str) -> AgentCard:
    """Return Alice's public A2A v1 Agent Card."""

    return AgentCard(
        name="Alice Personal Agent",
        description=(
            "An independent personal agent that evaluates trusted conference "
            "introductions without exposing private user context."
        ),
        supported_interfaces=[
            AgentInterface(
                url=f"{base_url.rstrip('/')}/a2a/alice",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["text/plain", "application/json"],
        default_output_modes=["application/json"],
        skills=[
            AgentSkill(
                id="trusted-introduction",
                name="Trusted introduction evaluation",
                description=(
                    "Evaluate a relationship-aware introduction request using "
                    "Alice's scoped context."
                ),
                tags=["relationships", "conference", "introduction"],
                examples=["Could you consider a relevant ICML introduction?"],
                input_modes=["application/json"],
                output_modes=["application/json"],
            )
        ],
    )


def create_app(
    *,
    base_url: str,
    project_id: str,
    model_id: str,
    location: str,
    persist_to_firestore: bool = False,
) -> Starlette:
    """Create an A2A server with explicit card and JSON-RPC endpoints."""

    card = build_alice_agent_card(base_url)
    provenance_store = (
        FirestoreProvenanceStore(project_id=project_id)
        if persist_to_firestore
        else InMemoryProvenanceStore()
    )
    executor = AliceAgentExecutor(
        project_id=project_id,
        model_id=model_id,
        location=location,
        provenance_store=provenance_store,
    )
    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    routes = [
        *create_agent_card_routes(card),
        *create_jsonrpc_routes(handler, rpc_url="/a2a/alice"),
    ]
    app = Starlette(routes=routes)
    app.state.a2a_handler = handler
    app.state.provenance_store = provenance_store
    app.state.agent_card = card
    return app

