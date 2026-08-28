"""Typed contracts shared by PairPilot services."""

from pairpilot_schemas.agent_messages import (
    A2AMessageEnvelope,
    A2AProposal,
    Claim,
    ClaimSource,
    PeerClaimDraft,
    PeerDecision,
    SpeechAct,
)
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
from pairpilot_schemas.introduction import IntroductionDecision

__all__ = [
    "A2AMessageEnvelope",
    "A2AProposal",
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
    "PeerClaimDraft",
    "PeerDecision",
    "Proposal",
    "RelationshipUpdate",
    "SpeechAct",
]
