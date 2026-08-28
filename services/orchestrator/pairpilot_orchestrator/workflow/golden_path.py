"""Authorized tools for the model-directed PairPilot golden path."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from time import perf_counter
from typing import Any, Literal
from uuid import UUID, uuid4

from pairpilot_schemas import (
    A2AProposal,
    Availability,
    EvidenceKind,
    EvidenceRecord,
    Proposal,
    SpeechAct,
)

from pairpilot_orchestrator.a2a_client import request_peer_agent
from pairpilot_orchestrator.domain.authority import (
    CoordinationAuthority,
    calculate_additional_cost,
    disclosure_hash,
)
from pairpilot_orchestrator.infrastructure import GoogleCloudStore
from pairpilot_orchestrator.policies.privacy import OutboundPrivacyGuard


class GoldenPathRuntime:
    """Stateful authority behind Qi's model-selected tools."""

    MAX_AGENT_TURNS = 12
    MAX_TOOL_CALLS = 16
    MAX_MESSAGES_PER_PAIR = 4
    MAX_ACTIVE_CANDIDATES = 2
    GOAL_START = date(2026, 7, 6)
    GOAL_END = date(2026, 7, 10)
    DELEGATED_MAXIMUM_USD = 70
    ROOM_RATE_USD = 124

    def __init__(
        self,
        *,
        store: GoogleCloudStore,
        peer_base_url: str,
        model_id: str,
        run_id: UUID | None = None,
        goal_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> None:
        self.store = store
        self.peer_base_url = peer_base_url
        self.model_id = model_id
        self.run_id = run_id or uuid4()
        self.goal_id = goal_id or uuid4()
        self.session_id = session_id or uuid4()
        self.authority = CoordinationAuthority()
        self.privacy = OutboundPrivacyGuard()
        self.tool_count = 0
        self.relationships_inspected: set[str] = set()
        self.discovered_agents: set[str] = set()
        self.warm_introduced_agents: set[str] = set()
        self.contacted_agents: set[str] = set()
        self.message_counts: dict[str, int] = {}
        self.beliefs: dict[str, dict[str, EvidenceRecord]] = {}
        self.dispositions: dict[str, str] = {}
        self.proposals: dict[UUID, Proposal] = {}
        self.status = "RUNNING"
        self.effect_contract: dict[str, Any] | None = None
        self.started_at = perf_counter()
        self.boundary_elapsed_ms: int | None = None
        self._peer_semaphore = asyncio.Semaphore(1)

    async def initialize(self, goal_text: str) -> None:
        """Create the run and intent before any agent turn."""

        now = datetime.now(UTC)
        await self.store.create(
            "runs",
            str(self.run_id),
            {
                "runId": str(self.run_id),
                "goalId": str(self.goal_id),
                "sessionId": str(self.session_id),
                "status": self.status,
                "exactModelId": self.model_id,
                "executionMode": "LIVE GEMINI + GOOGLE ADK + A2A",
                "startedAt": now,
                "maxAgentTurns": self.MAX_AGENT_TURNS,
                "maxToolCalls": self.MAX_TOOL_CALLS,
            },
        )
        await self.store.create(
            "intents",
            str(self.goal_id),
            {
                "goalId": str(self.goal_id),
                "runId": str(self.run_id),
                "ownerAgentId": "qi-agent",
                "goal": goal_text,
                "start": self.GOAL_START,
                "end": self.GOAL_END,
                "dominantPreference": "quiet overnight compatibility",
                "maximumAdditionalCostUsd": self.DELEGATED_MAXIMUM_USD,
                "commitmentBoundary": "current human approval required",
                "createdAt": now,
            },
        )
        await self._event(
            "intent.created",
            {"goalId": str(self.goal_id)},
            f"{self.run_id}:intent.created",
        )

    def tools(self) -> list[Any]:
        """Return the bounded tool surface made visible to Qi Agent."""

        return [
            self.inspect_relationship_network,
            self.search_open_agents,
            self.request_warm_introduction,
            self.contact_candidate,
            self.record_candidate_disposition,
            self.calculate_candidate_plan_cost,
            self.create_proposal,
            self.accept_proposal,
            self.send_proposal,
            self.place_soft_hold,
            self.request_user_approval,
            self.finish_no_match,
        ]

    def _before_tool(self) -> float:
        if self.status != "RUNNING":
            raise ValueError(f"run is not active: {self.status}")
        self.tool_count += 1
        if self.tool_count > self.MAX_TOOL_CALLS:
            self.status = "BOUNDED_NO_MATCH"
            raise ValueError("maximum tool-call bound reached")
        return perf_counter()

    async def _observe(
        self,
        *,
        tool: str,
        started: float,
        arguments: dict[str, Any],
        result: dict[str, Any],
        transition: str,
    ) -> dict[str, Any]:
        latency_ms = int((perf_counter() - started) * 1000)
        argument_digest = sha256(
            json.dumps(arguments, sort_keys=True).encode()
        ).hexdigest()
        await asyncio.gather(
            self.store.write_agent_turn(
                run_id=str(self.run_id),
                agent_id="qi-agent",
                session_id=str(self.session_id),
                model_id=self.model_id,
                permitted_context_ids=sorted(self.relationships_inspected),
                inbox_message_ids=[],
                selected_tool=tool,
                redacted_arguments=arguments,
                result=result,
                transition=transition,
                latency_ms=latency_ms,
            ),
            self._event(
                "agent.tool.completed",
                {"tool": tool, "transition": transition},
                f"{self.run_id}:tool:{tool}:{argument_digest}",
                publish_immediately=False,
            ),
        )
        return result

    async def _event(
        self,
        event_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
        *,
        publish_immediately: bool = True,
    ) -> dict[str, Any]:
        return await self.store.write_event(
            event_type=event_type,
            run_id=str(self.run_id),
            producer="qi-agent",
            payload=payload,
            idempotency_key=idempotency_key,
            publish_immediately=publish_immediately,
        )

    async def inspect_relationship_network(
        self, context: Literal["conference_coordination"]
    ) -> dict[str, Any]:
        """Inspect Qi's own contextual relationships before choosing a route."""

        started = self._before_tool()
        visible = []
        for relationship in await self.store.list_documents("relationships"):
            if relationship.get("sourceAgentId") != "qi-agent":
                continue
            relationship_id = str(relationship["_id"])
            self.relationships_inspected.add(relationship_id)
            visible.append(
                {
                    "relationship_id": relationship_id,
                    "context": relationship["context"],
                    "target_agent_id": relationship["targetAgentId"],
                    "relation_type": relationship["relationType"],
                    "coordination_reliability": relationship["coordinationReliability"],
                    "privacy_respect": relationship["privacyRespect"],
                    "provenance_event_ids": relationship["provenanceEventIds"],
                }
            )
        result = {
            "query_context": context,
            "relationships": visible,
        }
        return await self._observe(
            tool="inspect_relationship_network",
            started=started,
            arguments={"context": context},
            result=result,
            transition="relationship_context_loaded",
        )

    async def search_open_agents(
        self, conference: Literal["ICML"], gender: Literal["female"]
    ) -> dict[str, Any]:
        """Discover public open-network agents without reading private profiles."""

        started = self._before_tool()
        cards = await self.store.list_documents("agent_public_cards")
        matches = []
        for card in cards:
            if (
                card.get("openToColdContact") is True
                and card.get("verifiedConferenceAttendee") is True
                and str(card.get("conference", "")).casefold() == conference.casefold()
                and str(card.get("gender", "")).casefold() == gender.casefold()
            ):
                agent_id = str(card["agentId"])
                self.discovered_agents.add(agent_id)
                matches.append(
                    {
                        "agent_id": agent_id,
                        "verified_conference_attendee": True,
                        "conference": card["conference"],
                        "gender": card["gender"],
                        "availability": card.get("availability"),
                    }
                )
        result = {"matches": matches, "private_profiles_read": False}
        return await self._observe(
            tool="search_open_agents",
            started=started,
            arguments={"conference": conference, "gender": gender},
            result=result,
            transition="public_candidates_discovered",
        )

    async def request_warm_introduction(
        self, relationship_id: str, request_summary: str
    ) -> dict[str, Any]:
        """Ask the relationship owner to independently decide on an introduction."""

        started = self._before_tool()
        if relationship_id not in self.relationships_inspected:
            raise ValueError("relationship must be inspected before it can be used")
        relationship = await self.store.get("relationships", relationship_id)
        if relationship is None:
            raise ValueError("relationship no longer exists")
        safe_summary = self.privacy.validate(
            natural_language=request_summary, references=[]
        )
        async with self._peer_semaphore:
            result = await request_peer_agent(
                peer_base_url=self.peer_base_url,
                to_agent_id=str(relationship["targetAgentId"]),
                speech_act=SpeechAct.INTRODUCTION_REQUEST,
                natural_language=safe_summary,
                run_id=self.run_id,
                session_id=self.session_id,
            )
        introduced = [
            str(claim.value)
            for claim in result.response.claims
            if claim.field == "introduced_agent_id"
        ]
        self.warm_introduced_agents.update(introduced)
        await self._persist_exchange(result.response, route="warm_introduction")
        output = {
            "peer": result.response.from_agent_id,
            "speech_act": result.response.speech_act.value,
            "natural_language": result.response.natural_language,
            "introduced_agent_ids": introduced,
            "message_id": str(result.response.message_id),
            "retry_count": result.retry_count,
        }
        return await self._observe(
            tool="request_warm_introduction",
            started=started,
            arguments={
                "relationship_id": relationship_id,
                "request_summary": safe_summary,
            },
            result=output,
            transition="introduction_response_received",
        )

    async def contact_candidate(
        self, candidate_agent_id: str, question: str
    ) -> dict[str, Any]:
        """Ask a discovered or introduced candidate a minimum-necessary question."""

        started = self._before_tool()
        if candidate_agent_id not in (
            self.discovered_agents | self.warm_introduced_agents
        ):
            raise ValueError("candidate is neither publicly discovered nor introduced")
        if (
            candidate_agent_id not in self.contacted_agents
            and len(self.contacted_agents) >= self.MAX_ACTIVE_CANDIDATES
        ):
            raise ValueError("maximum active candidate negotiations reached")
        count = self.message_counts.get(candidate_agent_id, 0)
        if count >= self.MAX_MESSAGES_PER_PAIR:
            raise ValueError("maximum messages for this agent pair reached")
        safe_question = self.privacy.validate(natural_language=question, references=[])
        async with self._peer_semaphore:
            result = await request_peer_agent(
                peer_base_url=self.peer_base_url,
                to_agent_id=candidate_agent_id,
                speech_act=SpeechAct.INFORMATION_REQUEST,
                natural_language=safe_question,
                run_id=self.run_id,
                session_id=self.session_id,
            )
        self.contacted_agents.add(candidate_agent_id)
        self.message_counts[candidate_agent_id] = count + 1
        await self._persist_exchange(result.response, route="candidate_inquiry")
        claims = []
        for claim in result.response.claims:
            evidence = EvidenceRecord(
                subject_agent_id=candidate_agent_id,
                field=claim.field,
                value=claim.value,
                kind=EvidenceKind.REPORTED_CLAIM,
                source_message_id=str(result.response.message_id),
                confidence=claim.confidence,
            )
            self.beliefs.setdefault(candidate_agent_id, {})[claim.field] = evidence
            belief_id = sha256(
                f"{self.run_id}:{candidate_agent_id}:{claim.field}".encode()
            ).hexdigest()
            await self.store.upsert(
                "beliefs",
                belief_id,
                {
                    **evidence.model_dump(mode="json"),
                    "runId": str(self.run_id),
                    "authoritativeFact": False,
                },
            )
            claims.append(
                {
                    "field": claim.field,
                    "value": claim.value,
                    "evidence_kind": evidence.kind.value,
                    "confidence": claim.confidence,
                }
            )
        output = {
            "candidate_agent_id": candidate_agent_id,
            "speech_act": result.response.speech_act.value,
            "natural_language": result.response.natural_language,
            "claims": claims,
            "message_id": str(result.response.message_id),
            "retry_count": result.retry_count,
        }
        return await self._observe(
            tool="contact_candidate",
            started=started,
            arguments={
                "candidate_agent_id": candidate_agent_id,
                "question": safe_question,
            },
            result=output,
            transition="candidate_claims_recorded_as_beliefs",
        )

    async def record_candidate_disposition(
        self,
        candidate_agent_id: str,
        disposition: Literal["CONTINUE", "DEPRIORITIZE", "WITHDRAW"],
        observable_reason: str,
    ) -> dict[str, Any]:
        """Record Qi's evidence-based continue, deprioritize, or withdraw decision."""

        started = self._before_tool()
        if candidate_agent_id not in self.beliefs:
            raise ValueError("candidate has no received evidence")
        self.dispositions[candidate_agent_id] = disposition
        disposition_id = sha256(
            f"{self.run_id}:{candidate_agent_id}:disposition".encode()
        ).hexdigest()
        await self.store.upsert(
            "beliefs",
            disposition_id,
            {
                "runId": str(self.run_id),
                "subjectAgentId": candidate_agent_id,
                "field": "qi_disposition",
                "value": disposition,
                "kind": EvidenceKind.MODEL_INFERENCE.value,
                "observableReason": observable_reason,
                "authoritativeFact": False,
            },
        )
        output = {
            "candidate_agent_id": candidate_agent_id,
            "disposition": disposition,
            "observable_reason": observable_reason,
        }
        return await self._observe(
            tool="record_candidate_disposition",
            started=started,
            arguments=output,
            result=output,
            transition="candidate_disposition_recorded",
        )

    async def calculate_candidate_plan_cost(
        self, candidate_agent_id: str
    ) -> dict[str, Any]:
        """Calculate partial-overlap cost from authoritative availability."""

        started = self._before_tool()
        raw = await self.store.get("availability", candidate_agent_id)
        if raw is None:
            raise ValueError("candidate availability is unavailable")
        availability = Availability(
            candidate_agent_id=candidate_agent_id,
            start=date.fromisoformat(str(raw["start"])),
            end=date.fromisoformat(str(raw["end"])),
            active=bool(raw["active"]),
            version=int(raw["version"]),
        )
        self.authority.set_availability(availability)
        shared_start = max(self.GOAL_START, availability.start)
        shared_end = min(self.GOAL_END, availability.end)
        shared_nights = max(0, (shared_end - shared_start).days)
        total_nights = (self.GOAL_END - self.GOAL_START).days
        additional = calculate_additional_cost(
            total_nights=total_nights,
            shared_nights=shared_nights,
            nightly_room_cost_usd=self.ROOM_RATE_USD,
        )
        output = {
            "candidate_agent_id": candidate_agent_id,
            "total_nights": total_nights,
            "shared_nights": shared_nights,
            "shared_start": shared_start.isoformat(),
            "shared_end": shared_end.isoformat(),
            "nightly_room_cost_usd": self.ROOM_RATE_USD,
            "additional_cost_usd": additional,
            "delegated_maximum_usd": self.DELEGATED_MAXIMUM_USD,
            "within_delegated_authority": additional <= self.DELEGATED_MAXIMUM_USD,
            "availability_version": availability.version,
        }
        return await self._observe(
            tool="calculate_candidate_plan_cost",
            started=started,
            arguments={"candidate_agent_id": candidate_agent_id},
            result=output,
            transition="deterministic_cost_calculated",
        )

    async def create_proposal(
        self,
        candidate_agent_id: str,
        shared_start: str,
        shared_end: str,
        solo_dates: list[str],
    ) -> dict[str, Any]:
        """Create a versioned proposal only within verified delegated authority."""

        started = self._before_tool()
        if self.dispositions.get(candidate_agent_id) in {"DEPRIORITIZE", "WITHDRAW"}:
            raise ValueError("candidate negotiation is not active")
        if candidate_agent_id not in self.beliefs:
            raise ValueError("candidate must answer before a proposal is created")
        raw = await self.store.get("availability", candidate_agent_id)
        if raw is None:
            raise ValueError("candidate availability is unavailable")
        availability = Availability(
            candidate_agent_id=candidate_agent_id,
            start=date.fromisoformat(str(raw["start"])),
            end=date.fromisoformat(str(raw["end"])),
            active=bool(raw["active"]),
            version=int(raw["version"]),
        )
        self.authority.set_availability(availability)
        parsed_start = date.fromisoformat(shared_start)
        parsed_end = date.fromisoformat(shared_end)
        if not availability.covers(parsed_start, parsed_end):
            raise ValueError("proposal exceeds current candidate availability")
        total_nights = (self.GOAL_END - self.GOAL_START).days
        shared_nights = (parsed_end - parsed_start).days
        additional = calculate_additional_cost(
            total_nights=total_nights,
            shared_nights=shared_nights,
            nightly_room_cost_usd=self.ROOM_RATE_USD,
        )
        disclosures = [
            "conference and attendee verification",
            "shared and solo dates",
            "equal split for shared nights",
            "quiet overnight compatibility preference",
        ]
        proposal = Proposal(
            goal_id=self.goal_id,
            candidate_agent_id=candidate_agent_id,
            version=1,
            shared_start=parsed_start,
            shared_end=parsed_end,
            solo_dates=[date.fromisoformat(item) for item in solo_dates],
            additional_cost_usd=additional,
            delegated_maximum_usd=self.DELEGATED_MAXIMUM_USD,
            terms=[
                "Qi stays alone on each solo date.",
                "Qi and the candidate share on the shared dates.",
                "The shared nights are split equally.",
            ],
            disclosure_hash=disclosure_hash(disclosures),
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
        self.authority.add_proposal(proposal)
        self.proposals[proposal.proposal_id] = proposal
        payload = {
            **proposal.model_dump(mode="json"),
            "runId": str(self.run_id),
            "status": "PROPOSED",
            "availabilityVersion": availability.version,
            "disclosures": disclosures,
        }
        await self.store.create("proposals", str(proposal.proposal_id), payload)
        await self.store.create(
            "proposal_versions",
            f"{proposal.proposal_id}-v{proposal.version}",
            payload,
        )
        await self._event(
            "proposal.created",
            {
                "proposalId": str(proposal.proposal_id),
                "version": proposal.version,
            },
            f"{self.run_id}:proposal:{proposal.proposal_id}:v{proposal.version}",
        )
        output = {
            "proposal_id": str(proposal.proposal_id),
            "version": proposal.version,
            "candidate_agent_id": candidate_agent_id,
            "shared_start": shared_start,
            "shared_end": shared_end,
            "solo_dates": solo_dates,
            "additional_cost_usd": additional,
            "delegated_maximum_usd": self.DELEGATED_MAXIMUM_USD,
            "expires_at": proposal.expires_at.isoformat(),
        }
        return await self._observe(
            tool="create_proposal",
            started=started,
            arguments={
                "candidate_agent_id": candidate_agent_id,
                "shared_start": shared_start,
                "shared_end": shared_end,
                "solo_dates": solo_dates,
            },
            result=output,
            transition="versioned_proposal_created",
        )

    async def accept_proposal(self, proposal_id: str) -> dict[str, Any]:
        """Record Qi Agent's acceptance; this is not human commitment approval."""

        started = self._before_tool()
        proposal_uuid = UUID(proposal_id)
        self.authority.accept(proposal_uuid, agent_id="qi-agent")
        proposal = self.proposals[proposal_uuid]
        await self.store.upsert(
            "proposal_acceptances",
            f"{proposal_id}-v{proposal.version}-qi-agent",
            {
                "runId": str(self.run_id),
                "proposalId": proposal_id,
                "proposalVersion": proposal.version,
                "agentId": "qi-agent",
                "acceptedAt": datetime.now(UTC),
                "isHumanApproval": False,
            },
        )
        output = {
            "proposal_id": proposal_id,
            "proposal_version": proposal.version,
            "accepted_by": "qi-agent",
            "human_approval": False,
        }
        return await self._observe(
            tool="accept_proposal",
            started=started,
            arguments={"proposal_id": proposal_id},
            result=output,
            transition="qi_agent_accepted_proposal",
        )

    async def send_proposal(
        self, proposal_id: str, natural_language: str
    ) -> dict[str, Any]:
        """Send the current typed proposal for the candidate's own decision."""

        started = self._before_tool()
        proposal = self.proposals[UUID(proposal_id)]
        safe_message = self.privacy.validate(
            natural_language=natural_language, references=[]
        )
        async with self._peer_semaphore:
            result = await request_peer_agent(
                peer_base_url=self.peer_base_url,
                to_agent_id=proposal.candidate_agent_id,
                speech_act=SpeechAct.PROPOSAL,
                natural_language=safe_message,
                run_id=self.run_id,
                session_id=self.session_id,
                proposal=A2AProposal(
                    version=proposal.version,
                    shared_start=proposal.shared_start,
                    shared_end=proposal.shared_end,
                    solo_dates=proposal.solo_dates,
                    additional_cost_usd=proposal.additional_cost_usd,
                    cost_rule="equal_split_shared_nights",
                ),
            )
        await self._persist_exchange(result.response, route="proposal")
        accepted = (
            result.response.speech_act == SpeechAct.ACCEPTANCE
            and result.response.proposal is not None
            and result.response.proposal.version == proposal.version
        )
        if accepted:
            self.authority.accept(
                proposal.proposal_id, agent_id=proposal.candidate_agent_id
            )
            await self.store.upsert(
                "proposal_acceptances",
                f"{proposal_id}-v{proposal.version}-{proposal.candidate_agent_id}",
                {
                    "runId": str(self.run_id),
                    "proposalId": proposal_id,
                    "proposalVersion": proposal.version,
                    "agentId": proposal.candidate_agent_id,
                    "acceptedAt": datetime.now(UTC),
                    "sourceMessageId": str(result.response.message_id),
                    "isHumanApproval": False,
                },
            )
        output = {
            "proposal_id": proposal_id,
            "candidate_agent_id": proposal.candidate_agent_id,
            "speech_act": result.response.speech_act.value,
            "candidate_accepted_current_version": accepted,
            "natural_language": result.response.natural_language,
            "message_id": str(result.response.message_id),
            "retry_count": result.retry_count,
        }
        return await self._observe(
            tool="send_proposal",
            started=started,
            arguments={
                "proposal_id": proposal_id,
                "natural_language": safe_message,
            },
            result=output,
            transition=(
                "candidate_accepted_proposal"
                if accepted
                else "candidate_did_not_accept_proposal"
            ),
        )

    async def place_soft_hold(self, proposal_id: str) -> dict[str, Any]:
        """Place one expiring hold only after both personal agents accept."""

        started = self._before_tool()
        proposal = self.proposals[UUID(proposal_id)]
        accepted = self.authority.acceptances.get(
            (proposal.proposal_id, proposal.version), set()
        )
        if accepted != {"qi-agent", proposal.candidate_agent_id}:
            raise ValueError("both personal agents must accept before a hold")
        hold = self.authority.place_hold(
            proposal.proposal_id, expires_at=datetime.now(UTC) + timedelta(minutes=10)
        )
        await self.store.create(
            "holds",
            str(hold.hold_id),
            {**hold.model_dump(mode="json"), "runId": str(self.run_id)},
        )
        await self._event(
            "hold.created",
            {
                "holdId": str(hold.hold_id),
                "proposalId": proposal_id,
                "proposalVersion": proposal.version,
            },
            f"{self.run_id}:hold:{proposal_id}:v{proposal.version}",
        )
        output = {
            "hold_id": str(hold.hold_id),
            "proposal_id": proposal_id,
            "proposal_version": proposal.version,
            "expires_at": hold.expires_at.isoformat(),
            "active": hold.active,
        }
        return await self._observe(
            tool="place_soft_hold",
            started=started,
            arguments={"proposal_id": proposal_id},
            result=output,
            transition="transactional_hold_created",
        )

    async def request_user_approval(
        self, proposal_id: str, recommendation: str, remaining_uncertainty: str
    ) -> dict[str, Any]:
        """Pause at a complete effect contract; never approve on the user's behalf."""

        started = self._before_tool()
        proposal = self.proposals[UUID(proposal_id)]
        hold = next(
            (
                item
                for item in self.authority.holds.values()
                if item.proposal_id == proposal.proposal_id and item.active
            ),
            None,
        )
        if hold is None or hold.expires_at <= datetime.now(UTC):
            raise ValueError("active current hold required before approval request")
        accepted = self.authority.acceptances.get(
            (proposal.proposal_id, proposal.version), set()
        )
        if accepted != {"qi-agent", proposal.candidate_agent_id}:
            raise ValueError("both personal agents must accept before approval request")
        availability = self.authority.availability[proposal.candidate_agent_id]
        contract = {
            "candidateIdentitySummary": (
                f"{proposal.candidate_agent_id}: verified female ICML attendee"
            ),
            "sharedDates": {
                "start": proposal.shared_start.isoformat(),
                "end": proposal.shared_end.isoformat(),
            },
            "soloDates": [item.isoformat() for item in proposal.solo_dates],
            "costDifferenceUsd": proposal.additional_cost_usd,
            "delegatedMaximumUsd": proposal.delegated_maximum_usd,
            "agreedTerms": proposal.terms,
            "remainingUncertainty": remaining_uncertainty,
            "recommendation": recommendation,
            "informationDisclosed": [
                "conference eligibility",
                "dates and cost split",
                "quiet overnight compatibility preference",
            ],
            "informationRemainingPrivate": [
                "One protected sleep-related fact and all raw private memory"
            ],
            "proposalId": proposal_id,
            "proposalVersion": proposal.version,
            "disclosureHash": proposal.disclosure_hash,
            "holdId": str(hold.hold_id),
            "holdExpiresAt": hold.expires_at.isoformat(),
            "currentAvailabilityStatus": {
                "active": availability.active,
                "version": availability.version,
                "coversSharedDates": availability.covers(
                    proposal.shared_start, proposal.shared_end
                ),
            },
        }
        approval_request_id = f"{proposal_id}-v{proposal.version}"
        await self.store.upsert(
            "approval_requests",
            approval_request_id,
            {
                "runId": str(self.run_id),
                "status": "AWAITING_HUMAN",
                **contract,
                "requestedAt": datetime.now(UTC),
            },
        )
        self.effect_contract = contract
        self.status = "WAITING_FOR_HUMAN_APPROVAL"
        self.boundary_elapsed_ms = int((perf_counter() - self.started_at) * 1000)
        await self.store.upsert(
            "runs",
            str(self.run_id),
            {
                "runId": str(self.run_id),
                "goalId": str(self.goal_id),
                "sessionId": str(self.session_id),
                "status": self.status,
                "exactModelId": self.model_id,
                "executionMode": "LIVE GEMINI + GOOGLE ADK + A2A",
                "currentProposalId": proposal_id,
                "currentProposalVersion": proposal.version,
                "updatedAt": datetime.now(UTC),
            },
        )
        await self._event(
            "approval.requested",
            {"proposalId": proposal_id, "proposalVersion": proposal.version},
            f"{self.run_id}:approval.requested:{proposal_id}:v{proposal.version}",
        )
        output = {"status": self.status, "effect_contract": contract}
        return await self._observe(
            tool="request_user_approval",
            started=started,
            arguments={
                "proposal_id": proposal_id,
                "recommendation": recommendation,
                "remaining_uncertainty": remaining_uncertainty,
            },
            result=output,
            transition="paused_at_human_approval_boundary",
        )

    async def finish_no_match(self, observable_reason: str) -> dict[str, Any]:
        """Terminate safely when the evidence does not justify a match."""

        started = self._before_tool()
        self.status = "NO_MATCH"
        await self.store.upsert(
            "runs",
            str(self.run_id),
            {
                "runId": str(self.run_id),
                "goalId": str(self.goal_id),
                "sessionId": str(self.session_id),
                "status": self.status,
                "terminationReason": observable_reason,
                "updatedAt": datetime.now(UTC),
            },
        )
        await self._event(
            "run.completed",
            {"status": self.status},
            f"{self.run_id}:run.completed:no-match",
        )
        output = {"status": self.status, "observable_reason": observable_reason}
        return await self._observe(
            tool="finish_no_match",
            started=started,
            arguments={"observable_reason": observable_reason},
            result=output,
            transition="safe_no_match_terminal",
        )

    async def _persist_exchange(self, envelope: Any, *, route: str) -> None:
        await self.store.create(
            "agent_messages",
            str(envelope.message_id),
            {
                **envelope.model_dump(mode="json"),
                "route": route,
                "receivedAt": datetime.now(UTC),
                "claimsAreAuthoritativeFacts": False,
            },
        )
        await self._event(
            "agent.message.received",
            {
                "messageId": str(envelope.message_id),
                "fromAgentId": envelope.from_agent_id,
                "toAgentId": envelope.to_agent_id,
                "speechAct": envelope.speech_act.value,
            },
            f"{self.run_id}:message.received:{envelope.message_id}",
        )
