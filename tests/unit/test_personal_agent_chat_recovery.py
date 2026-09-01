from pairpilot_orchestrator.personal_agent_chat import (
    authoritative_tool_recovery_message,
)


def test_recovery_reports_persisted_draft_without_claiming_model_completion() -> None:
    message = authoritative_tool_recovery_message(
        [{"name": "revise_intent_post", "result": {"status": "DRAFTED"}}]
    )

    assert "saved" in message
    assert "no action was lost" in message
    assert "model response was interrupted" in message


def test_recovery_reports_authoritative_publish() -> None:
    message = authoritative_tool_recovery_message(
        [{"name": "publish_intent_post", "result": {"status": "PUBLISHED"}}]
    )

    assert "published and open for matching" in message
    assert "authoritative publish succeeded" in message
