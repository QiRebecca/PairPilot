from pairpilot_orchestrator.tools.runtime import verify_runtime_identity


def test_runtime_marker_is_deterministic() -> None:
    assert verify_runtime_identity("qi-agent") == {
        "component": "qi-agent",
        "status": "verified",
        "runtime": "google-adk-2.8.0",
    }

