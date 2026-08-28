from datetime import date
from uuid import uuid4

import pytest
from pairpilot_schemas import A2AMessageEnvelope, A2AProposal, SpeechAct
from pydantic import ValidationError


def test_proposal_is_negotiation_data_not_commitment() -> None:
    envelope = A2AMessageEnvelope(
        run_id=uuid4(),
        session_id=uuid4(),
        from_agent_id="qi-agent",
        to_agent_id="maya-agent",
        speech_act=SpeechAct.PROPOSAL,
        natural_language="Could Maya consider sharing July 7 through July 10?",
        proposal=A2AProposal(
            version=1,
            shared_start=date(2026, 7, 7),
            shared_end=date(2026, 7, 10),
            solo_dates=[date(2026, 7, 6)],
            additional_cost_usd=62,
            cost_rule="equal_split_shared_nights",
        ),
    )
    assert envelope.proposal is not None
    assert envelope.proposal.additional_cost_usd == 62
    assert not hasattr(envelope, "committed")


def test_invalid_proposal_date_order_is_rejected() -> None:
    with pytest.raises(ValidationError):
        A2AProposal(
            version=1,
            shared_start=date(2026, 7, 10),
            shared_end=date(2026, 7, 7),
            additional_cost_usd=62,
            cost_rule="equal_split_shared_nights",
        )
