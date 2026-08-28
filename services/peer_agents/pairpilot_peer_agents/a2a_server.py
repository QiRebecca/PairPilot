"""Starlette service exposing three logically independent A2A 1.x agents."""

from dataclasses import dataclass

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from starlette.applications import Starlette

from pairpilot_peer_agents.a2a_executor import AgentBuilder, PeerAgentExecutor
from pairpilot_peer_agents.agents import (
    build_alice_agent,
    build_lena_agent,
    build_maya_agent,
)
from pairpilot_peer_agents.provenance import (
    FirestoreProvenanceStore,
    InMemoryProvenanceStore,
)


@dataclass(frozen=True)
class PeerDefinition:
    agent_id: str
    slug: str
    owner_id: str
    display_name: str
    description: str
    skill: AgentSkill
    builder: AgentBuilder


PEERS = (
    PeerDefinition(
        agent_id="alice-agent",
        slug="alice",
        owner_id="alice-owner",
        display_name="Alice Personal Agent",
        description=(
            "An independent personal agent that evaluates trusted conference "
            "introductions without exposing private user context."
        ),
        skill=AgentSkill(
            id="trusted-introduction",
            name="Trusted introduction evaluation",
            description="Evaluate a relationship-aware introduction request.",
            tags=["relationships", "conference", "introduction"],
            examples=["Could you consider a relevant ICML introduction?"],
            input_modes=["application/json"],
            output_modes=["application/json"],
        ),
        builder=build_alice_agent,
    ),
    PeerDefinition(
        agent_id="maya-agent",
        slug="maya",
        owner_id="maya-owner",
        display_name="Maya Personal Agent",
        description=(
            "An independent personal agent that answers scoped roommate questions "
            "and evaluates proposals for Maya."
        ),
        skill=AgentSkill(
            id="roommate-coordination",
            name="Roommate coordination",
            description="Share permitted claims and evaluate proposal versions.",
            tags=["conference", "roommate", "negotiation"],
            examples=["Would your user consider this three-night proposal?"],
            input_modes=["application/json"],
            output_modes=["application/json"],
        ),
        builder=build_maya_agent,
    ),
    PeerDefinition(
        agent_id="lena-agent",
        slug="lena",
        owner_id="lena-owner",
        display_name="Lena Personal Agent",
        description=(
            "An independent personal agent that answers scoped roommate questions "
            "and evaluates proposals for Lena."
        ),
        skill=AgentSkill(
            id="roommate-coordination",
            name="Roommate coordination",
            description="Share permitted claims and evaluate proposal versions.",
            tags=["conference", "roommate", "negotiation"],
            examples=["Are there routine constraints relevant to sharing a room?"],
            input_modes=["application/json"],
            output_modes=["application/json"],
        ),
        builder=build_lena_agent,
    ),
)


def build_agent_card(peer: PeerDefinition, base_url: str) -> AgentCard:
    """Return one peer's public A2A v1 Agent Card."""

    return AgentCard(
        name=peer.display_name,
        description=peer.description,
        supported_interfaces=[
            AgentInterface(
                url=f"{base_url.rstrip('/')}/a2a/{peer.slug}",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
        version="0.2.0",
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["text/plain", "application/json"],
        default_output_modes=["application/json"],
        skills=[peer.skill],
    )


def build_alice_agent_card(base_url: str) -> AgentCard:
    """Backward-compatible helper for the default public card."""

    return build_agent_card(PEERS[0], base_url)


def create_app(
    *,
    base_url: str,
    project_id: str,
    model_id: str,
    location: str,
    persist_to_firestore: bool = False,
) -> Starlette:
    """Create independent official card and JSON-RPC routes for every peer."""

    routes = []
    handlers = {}
    cards = {}
    stores = {}
    for peer in PEERS:
        card = build_agent_card(peer, base_url)
        store = (
            FirestoreProvenanceStore(
                project_id=project_id,
                from_agent_id=peer.agent_id,
            )
            if persist_to_firestore
            else InMemoryProvenanceStore(from_agent_id=peer.agent_id)
        )
        executor = PeerAgentExecutor(
            agent_id=peer.agent_id,
            owner_id=peer.owner_id,
            agent_builder=peer.builder,
            project_id=project_id,
            model_id=model_id,
            location=location,
            provenance_store=store,
        )
        handler = DefaultRequestHandler(
            agent_executor=executor,
            task_store=InMemoryTaskStore(),
            agent_card=card,
        )
        card_path = f"/.well-known/agents/{peer.agent_id}.json"
        routes.extend(create_agent_card_routes(card, card_url=card_path))
        if peer.agent_id == "alice-agent":
            routes.extend(create_agent_card_routes(card))
        routes.extend(create_jsonrpc_routes(handler, rpc_url=f"/a2a/{peer.slug}"))
        handlers[peer.agent_id] = handler
        cards[peer.agent_id] = card
        stores[peer.agent_id] = store

    app = Starlette(routes=routes)
    app.state.a2a_handlers = handlers
    app.state.agent_cards = cards
    app.state.provenance_stores = stores
    app.state.a2a_handler = handlers["alice-agent"]
    app.state.agent_card = cards["alice-agent"]
    app.state.provenance_store = stores["alice-agent"]
    return app
