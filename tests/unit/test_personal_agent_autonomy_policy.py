from pairpilot_orchestrator.personal_agent_chat import (
    _effective_autonomy_actions,
    _publish_policy_decision,
)


def test_publish_policy_never_blocks_even_explicit_confirmation() -> None:
    assert (
        _publish_policy_decision(
            publish_level="NEVER",
            confirmation="PUBLISH THIS POST",
            authorizing_user_content="Publish it now.",
        )
        == "BLOCKED_BY_AUTONOMY_POLICY"
    )


def test_publish_policy_ask_first_requires_phrase_and_current_user_authority() -> None:
    assert (
        _publish_policy_decision(
            publish_level="ASK_FIRST",
            confirmation="PUBLISH THIS POST",
            authorizing_user_content="Please revise the draft.",
        )
        == "REQUIRES_HUMAN_CONFIRMATION"
    )
    assert (
        _publish_policy_decision(
            publish_level="ASK_FIRST",
            confirmation="PUBLISH THIS POST",
            authorizing_user_content="Go ahead and publish it.",
        )
        == "AUTHORIZED"
    )


def test_publish_policy_automatic_does_not_require_confirmation() -> None:
    assert (
        _publish_policy_decision(
            publish_level="AUTOMATIC",
            confirmation="",
            authorizing_user_content="Prepare the Post.",
        )
        == "AUTHORIZED"
    )


def test_task_override_is_visible_to_agent_but_final_commitment_stays_locked() -> (
    None
):
    actions = _effective_autonomy_actions(
        {
            "action_levels": {
                "PUBLISH_POST": "ASK_FIRST",
                "APPROVE_FINAL_COMMITMENT": "NEVER",
            }
        },
        {
            "action_levels": {
                "PUBLISH_POST": "AUTOMATIC",
                "APPROVE_FINAL_COMMITMENT": "AUTOMATIC",
            }
        },
    )

    assert actions["PUBLISH_POST"] == "AUTOMATIC"
    assert actions["APPROVE_FINAL_COMMITMENT"] == "ASK_FIRST"
