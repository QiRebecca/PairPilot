import importlib.util
from pathlib import Path


def load_seed_module():
    path = Path(__file__).parents[2] / "infra" / "seed_demo.py"
    spec = importlib.util.spec_from_file_location("seed_demo", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_contains_no_workflow_trajectory() -> None:
    seed_demo = load_seed_module()
    data = seed_demo.documents()
    forbidden = {
        "agent_messages",
        "beliefs",
        "proposals",
        "proposal_versions",
        "holds",
        "approvals",
        "matches",
        "runs",
    }
    assert forbidden.isdisjoint(data)
    assert not data["seed_metadata"]["pairpilot-demo-v1"][
        "containsWorkflowTrajectory"
    ]


def test_private_profiles_are_agent_scoped() -> None:
    seed_demo = load_seed_module()
    profiles = seed_demo.documents()["agent_private_profiles"]
    for agent_id, profile in profiles.items():
        assert profile["readableBy"] == [agent_id]

