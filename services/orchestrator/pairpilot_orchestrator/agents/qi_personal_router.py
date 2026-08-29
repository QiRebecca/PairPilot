"""Persistent Qi Agent router for global and task-scoped user messages."""

from google import genai
from google.adk.agents import Agent
from google.adk.models import Gemini
from pairpilot_schemas import PersonalAgentRoutingResult

from pairpilot_orchestrator.config import Settings


def build_qi_personal_router_agent(settings: Settings) -> Agent:
    """Build one typed router; it classifies semantics without keyword branches."""

    model = Gemini(
        model=settings.model_id,
        api_version="v1",
        client_kwargs={
            "enterprise": True,
            "project": settings.project_id,
            "location": settings.model_location,
        },
    )
    return Agent(
        name="qi_personal_agent_router",
        model=model,
        description="Qi's persistent Personal Agent conversation router.",
        instruction=(
            "You are the same persistent Qi Agent across many isolated task "
            "workspaces. Classify the current user message into the exact typed "
            "PersonalAgentRoutingResult. The prompt contains only bounded task "
            "summaries, never full task transcripts. NEW_TASK is only for a new "
            "real-world coordination request. EXISTING_TASK_UPDATE changes one "
            "unambiguous task. If an update could apply to more than one task, use "
            "CLARIFICATION_REQUIRED and do not select the most recent task. Use "
            "presentation_actions only from the schema allowlist. Do not invent "
            "facts, entity IDs, URLs, approvals, matches, relationships or memory. "
            "Keep response_text concise and observable. The infrastructure will "
            "fetch authoritative entities and execute any allowed action."
        ),
        output_schema=PersonalAgentRoutingResult,
        generate_content_config=genai.types.GenerateContentConfig(
            max_output_tokens=768,
            thinking_config=genai.types.ThinkingConfig(
                thinking_level=genai.types.ThinkingLevel.LOW
            ),
        ),
    )
