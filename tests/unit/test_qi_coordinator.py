from google.genai.types import ThinkingLevel
from pairpilot_orchestrator.agents import build_qi_coordinator_agent
from pairpilot_orchestrator.config import Settings


class FakeRuntime:
    def tools(self):
        return []


def test_qi_coordinator_is_live_and_has_no_output_schema_story() -> None:
    agent = build_qi_coordinator_agent(
        Settings(project_id="test-project"),
        runtime=FakeRuntime(),  # type: ignore[arg-type]
    )
    assert agent.name == "qi_agent"
    assert agent.model.model == "gemini-3.7-flash"
    assert agent.output_schema is None
    assert (
        agent.generate_content_config.thinking_config.thinking_level
        == ThinkingLevel.LOW
    )


def test_tool_surface_exposes_bounded_batch_contact_only() -> None:
    runtime = FakeRuntime()
    runtime.tools = lambda: []
    agent = build_qi_coordinator_agent(
        Settings(project_id="test-project"),
        runtime=runtime,  # type: ignore[arg-type]
    )
    assert "contact_candidates" in agent.instruction
