from uuid import uuid4

import pytest
from pairpilot_schemas import A2AMessageEnvelope, SpeechAct, canonical_intent_pair
from pydantic import ValidationError


def test_a2a_envelope_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        source_intent_id = "intent_qi_icml_roommate"
        A2AMessageEnvelope(
            run_id=uuid4(),
            session_id=uuid4(),
            from_agent_id="qi-agent",
            to_agent_id="alice-agent",
            from_intent_id=source_intent_id,
            to_intent_id=source_intent_id,
            pair_session_id=canonical_intent_pair(source_intent_id, source_intent_id),
            speech_act=SpeechAct.INTRODUCTION_REQUEST,
            natural_language="Could you consider a relevant introduction?",
            hidden_private_context="must never cross the boundary",
        )
