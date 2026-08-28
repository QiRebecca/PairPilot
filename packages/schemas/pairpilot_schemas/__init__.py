"""Typed contracts shared by PairPilot services."""

from pairpilot_schemas.agent_messages import (
    A2AMessageEnvelope,
    Claim,
    ClaimSource,
    SpeechAct,
)
from pairpilot_schemas.introduction import IntroductionDecision
from pairpilot_schemas.domain import (
    Approval,
    Availability,
    EvidenceKind,
    EvidenceRecord,
    Hold,
    Match,
    MemoryRecord,
    Proposal,
    RelationshipUpdate,
)

__all__ = [
    "A2AMessageEnvelope",
    "Approval",
    "Availability",
    "Claim",
    "ClaimSource",
    "EvidenceKind",
    "EvidenceRecord",
    "Hold",
    "IntroductionDecision",
    "Match",
    "MemoryRecord",
    "Proposal",
    "RelationshipUpdate",
    "SpeechAct",
]
