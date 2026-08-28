"""Deterministic proposal, hold, approval, and commitment authority."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from pairpilot_schemas import (
    Approval,
    Availability,
    Hold,
    Match,
    MemoryRecord,
    Proposal,
    RelationshipUpdate,
)


class AuthorityError(ValueError):
    """A requested state transition violated an authoritative invariant."""


def disclosure_hash(disclosures: list[str]) -> str:
    """Hash a canonical disclosure contract for commit-time comparison."""

    canonical = "\n".join(sorted(item.strip() for item in disclosures))
    return sha256(canonical.encode()).hexdigest()


def calculate_additional_cost(
    *, total_nights: int, shared_nights: int, nightly_room_cost_usd: int
) -> int:
    """Compare partial sharing with an equal split across every night."""

    if not 0 <= shared_nights <= total_nights:
        raise AuthorityError("shared_nights must be within total_nights")
    if nightly_room_cost_usd < 0:
        raise AuthorityError("nightly_room_cost_usd cannot be negative")
    baseline_cents = total_nights * nightly_room_cost_usd * 100 // 2
    solo_nights = total_nights - shared_nights
    partial_cents = (
        solo_nights * nightly_room_cost_usd * 100
        + shared_nights * nightly_room_cost_usd * 100 // 2
    )
    return (partial_cents - baseline_cents) // 100


class CoordinationAuthority:
    """In-memory reference engine; Firestore transactions use the same checks."""

    def __init__(self) -> None:
        self.proposals: dict[UUID, Proposal] = {}
        self.holds: dict[UUID, Hold] = {}
        self.approvals: dict[UUID, Approval] = {}
        self.acceptances: dict[tuple[UUID, int], set[str]] = {}
        self.availability: dict[str, Availability] = {}
        self.matches_by_proposal: dict[UUID, Match] = {}
        self.relationship_updates: list[RelationshipUpdate] = []
        self.memories: list[MemoryRecord] = []

    def set_availability(self, availability: Availability) -> None:
        self.availability[availability.candidate_agent_id] = availability

    def add_proposal(self, proposal: Proposal) -> None:
        existing_versions = [
            item.version
            for item in self.proposals.values()
            if (
                (
                    item.source_intent_id == proposal.source_intent_id
                    and item.target_intent_id == proposal.target_intent_id
                )
                if proposal.source_intent_id
                else (
                    item.goal_id == proposal.goal_id
                    and item.candidate_agent_id == proposal.candidate_agent_id
                )
            )
        ]
        expected = max(existing_versions, default=0) + 1
        if proposal.version != expected:
            raise AuthorityError(f"expected proposal version {expected}")
        if proposal.expires_at.tzinfo is None:
            raise AuthorityError("proposal expiry must be timezone-aware")
        if proposal.additional_cost_usd > proposal.delegated_maximum_usd:
            raise AuthorityError("proposal exceeds delegated cost authority")
        self.proposals[proposal.proposal_id] = proposal

    def place_hold(self, proposal_id: UUID, *, expires_at: datetime) -> Hold:
        proposal = self.proposals[proposal_id]
        now = datetime.now(UTC)
        if expires_at <= now:
            raise AuthorityError("hold must expire in the future")
        for hold in self.holds.values():
            proposal_intents = {
                item
                for item in (proposal.source_intent_id, proposal.target_intent_id)
                if item is not None
            }
            held_intents = {
                item
                for item in (hold.source_intent_id, hold.target_intent_id)
                if item is not None
            }
            same_capacity = (
                bool(proposal_intents & held_intents)
                if proposal_intents
                else hold.goal_id == proposal.goal_id
            )
            if same_capacity and hold.active:
                if hold.expires_at > now:
                    raise AuthorityError("a conflicting active hold already exists")
                hold.active = False
        hold = Hold(
            proposal_id=proposal.proposal_id,
            proposal_version=proposal.version,
            goal_id=proposal.goal_id,
            source_intent_id=proposal.source_intent_id,
            target_intent_id=proposal.target_intent_id,
            pair_session_id=proposal.pair_session_id,
            candidate_agent_id=proposal.candidate_agent_id,
            idempotency_key=(
                f"{proposal.pair_session_id}:v{proposal.version}"
                if proposal.pair_session_id
                else None
            ),
            expires_at=expires_at,
        )
        self.holds[hold.hold_id] = hold
        return hold

    def accept(self, proposal_id: UUID, *, agent_id: str) -> None:
        proposal = self.proposals[proposal_id]
        permitted = {"qi-agent", proposal.candidate_agent_id}
        if agent_id not in permitted:
            raise AuthorityError("agent cannot accept this proposal")
        self.acceptances.setdefault(
            (proposal.proposal_id, proposal.version), set()
        ).add(agent_id)

    def approve(
        self,
        proposal_id: UUID,
        *,
        proposal_version: int,
        current_disclosure_hash: str,
    ) -> Approval:
        if proposal_id not in self.proposals:
            raise AuthorityError("proposal does not exist")
        approval = Approval(
            proposal_id=proposal_id,
            proposal_version=proposal_version,
            disclosure_hash=current_disclosure_hash,
        )
        self.approvals[proposal_id] = approval
        return approval

    def commit(self, proposal_id: UUID, *, now: datetime) -> Match:
        if proposal_id in self.matches_by_proposal:
            return self.matches_by_proposal[proposal_id]
        proposal = self.proposals[proposal_id]
        if now.tzinfo is None:
            raise AuthorityError("commit time must be timezone-aware")
        if proposal.expires_at <= now:
            raise AuthorityError("proposal expired")

        hold = next(
            (
                item
                for item in self.holds.values()
                if item.proposal_id == proposal_id
                and item.proposal_version == proposal.version
                and item.active
            ),
            None,
        )
        if hold is None or hold.expires_at <= now:
            raise AuthorityError("active current hold required")

        availability = self.availability.get(proposal.candidate_agent_id)
        if availability is None or not availability.covers(
            proposal.shared_start, proposal.shared_end
        ):
            raise AuthorityError("candidate is no longer available")

        accepted = self.acceptances.get((proposal.proposal_id, proposal.version), set())
        if accepted != {"qi-agent", proposal.candidate_agent_id}:
            raise AuthorityError("both personal agents must accept")

        approval = self.approvals.get(proposal_id)
        if approval is None:
            raise AuthorityError("current human approval required")
        if approval.proposal_version != proposal.version:
            raise AuthorityError("approval references an old proposal version")
        if approval.disclosure_hash != proposal.disclosure_hash:
            raise AuthorityError("disclosure scope changed after approval")

        commit_event_id = uuid4()
        match = Match(
            proposal_id=proposal_id,
            proposal_version=proposal.version,
            committed_at=now,
            provenance_event_ids=[commit_event_id],
        )
        self.matches_by_proposal[proposal_id] = match
        hold.active = False
        self.relationship_updates.append(
            RelationshipUpdate(
                source_agent_id="qi-agent",
                target_agent_id=proposal.candidate_agent_id,
                context="conference_roommate_coordination",
                relation_type="successful_coordination",
                successful_plans_delta=1,
                provenance_event_ids=[commit_event_id],
            )
        )
        self.memories.append(
            MemoryRecord(
                owner_agent_id="qi-agent",
                memory_type="inferred_preference",
                content=(
                    "The user accepted partial date coverage to preserve "
                    "quiet-room compatibility."
                ),
                scope="hotel_sharing",
                source="approved_successful_coordination",
                confidence=0.78,
                sensitivity="personal_preference",
                confirmation_status="editable_inference",
                provenance_event_ids=[commit_event_id],
                decay_policy="review_after_180_days",
            )
        )
        return match
