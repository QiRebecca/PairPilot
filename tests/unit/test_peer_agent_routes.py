from pairpilot_peer_agents.a2a_server import PEERS, create_app


def test_every_peer_has_independent_card_route_and_rpc_route() -> None:
    app = create_app(
        base_url="https://peer.example",
        project_id="test-project",
        model_id="gemini-3.7-flash",
        location="global",
    )
    route_paths = [route.path for route in app.routes]
    for peer in PEERS:
        assert f"/.well-known/agents/{peer.agent_id}.json" in route_paths
        assert f"/a2a/{peer.slug}" in route_paths
    assert set(app.state.a2a_handlers) == {
        "alice-agent",
        "maya-agent",
        "lena-agent",
    }
    assert len({id(value) for value in app.state.a2a_handlers.values()}) == 3
    assert len({id(value) for value in app.state.provenance_stores.values()}) == 3
