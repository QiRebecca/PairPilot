from uuid import uuid4

import pytest
from pairpilot_schemas import A2AMessageEnvelope, SpeechAct
from pydantic import ValidationError


def test_a2a_envelope_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        A2AMessageEnvelope(
            run_id=uuid4(),
            session_id=uuid4(),
            from_agent_id="qi-agent",
            to_agent_id="alice-agent",
            speech_act=SpeechAct.INTRODUCTION_REQUEST,
            natural_language="Could you consider a relevant introduction?",
            hidden_private_context="must never cross the boundary",
        )
