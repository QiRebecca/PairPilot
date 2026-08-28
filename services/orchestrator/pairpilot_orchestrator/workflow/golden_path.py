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
    IntentStatus,
    Proposal,
    SpeechAct,
    canonical_intent_pair,
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
        source_intent_id: str,
    ) -> None:
        self.store = store
        self.peer_base_url = peer_base_url
        self.model_id = model_id
        self.run_id = run_id or uuid4()
        self.goal_id = goal_id or uuid4()
        self.source_intent_id = source_intent_id
        self.session_id = session_id or uuid4()
        self.authority = CoordinationAuthority()
        self.privacy = OutboundPrivacyGuard()
        self.tool_count = 0
        self.relationships_inspected: set[str] = set()
        self.discovered_intents: dict[str, str] = {}
        self.warm_introduced_intents: dict[str, str] = {}
        self.contacted_intents: set[str] = set()
        self.message_counts: dict[str, int] = {}
        self.beliefs: dict[str, dict[str, EvidenceRecord]] = {}
        self.dispositions: dict[str, str] = {}
        self.proposals: dict[UUID, Proposal] = {}
        self.status = "RUNNING"
        self.effect_contract: dict[str, Any] | None = None
        self.started_at = perf_counter()
        self.boundary_elapsed_ms: int | None = None
        self.goal_start = date.min
        self.goal_end = date.min
        self.delegated_maximum_usd = 0
        self.goal_text = ""
        self._peer_semaphore = asyncio.Semaphore(self.MAX_ACTIVE_CANDIDATES)

    async def initialize(self) -> str:
        """Load one user-published OPEN intent before any agent turn."""

        now = datetime.now(UTC)
        intent = await self.store.get("intents", self.source_intent_id)
        private = await self.store.get("intent_private", self.source_intent_id)
        if intent is None or private is None:
            raise ValueError("published source intent and owner context are required")
        if intent.get("owner_agent_id") != "qi-agent":
            raise ValueError("source intent does not belong to Qi Agent")
        if intent.get("status") != IntentStatus.OPEN.value:
            raise ValueError("source intent must be OPEN before the agent can run")
        if int(intent.get("capacity_remaining", 0)) < 1:
            raise ValueError("source intent has no remaining capacity")
        constraints = dict(intent["public_constraints"])
        boundaries = dict(intent["negotiation_boundaries"])
        self.goal_start = date.fromisoformat(str(constraints["date_start"]))
        self.goal_end = date.fromisoformat(str(constraints["date_end"]))
        self.delegated_maximum_usd = int(boundaries["maximum_additional_cost_usd"])
        self.goal_text = str(private["raw_user_goal"])
        await self.store.create(
            "runs",
            str(self.run_id),
            {
                "runId": str(self.run_id),
                "goalId": str(self.goal_id),
                "sourceIntentId": self.source_intent_id,
                "sessionId": str(self.session_id),
                "status": self.status,
                "exactModelId": self.model_id,
                "executionMode": "LIVE GEMINI + GOOGLE ADK + A2A",
                "startedAt": now,
                "maxAgentTurns": self.MAX_AGENT_TURNS,
                "maxToolCalls": self.MAX_TOOL_CALLS,
            },
        )
        intent.pop("_updateTime", None)
        intent.update(
            status=IntentStatus.NEGOTIATING.value, active_run_id=str(self.run_id)
        )
        await self.store.upsert("intents", self.source_intent_id, intent)
        await self._event(
            "intent.negotiation_started",
            {"intentId": self.source_intent_id},
            f"{self.run_id}:intent.negotiation_started:{self.source_intent_id}",
        )
        return self.goal_text

    def tools(self) -> list[Any]:
        """Return the bounded tool surface made visible to Qi Agent."""

        return [
            self.inspect_relationship_network,
            self.search_open_intents,
            self.request_warm_introduction,
            self.contact_candidates,
            self.record_candidate_disposition,
            self.calculate_candidate_plan_cost,
            self.create_proposal,
            self.accept_proposal,
            self.send_proposal,
            self.place_soft_hold_and_request_user_approval,
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

    async def search_open_intents(
        self,
        intent_type: Literal["conference_room_share"],
        location: Literal["Seoul"],
    ) -> dict[str, Any]:
        """Search current public posts without reading owners' private context."""

        started = self._before_tool()
        now = datetime.now(UTC)
        matches: list[dict[str, Any]] = []
        for intent in await self.store.list_documents("intents"):
            intent_id = str(intent.get("intent_id") or intent.get("_id"))
            if intent_id == self.source_intent_id:
                continue
            constraints = dict(intent.get("public_constraints") or {})
            expires_at = datetime.fromisoformat(
                str(intent.get("expires_at", "1970-01-01T00:00:00Z")).replace(
                    "Z", "+00:00"
                )
            )
            candidate_start = date.fromisoformat(
                str(constraints.get("date_start", "1970-01-01"))
            )
            candidate_end = date.fromisoformat(
                str(constraints.get("date_end", "1970-01-01"))
            )
            overlaps = max(self.goal_start, candidate_start) < min(
                self.goal_end, candidate_end
            )
            if not (
                intent.get("status") == IntentStatus.OPEN.value
                and intent.get("intent_type") == intent_type
                and str(constraints.get("location", "")).casefold()
                == location.casefold()
                and overlaps
                and int(intent.get("capacity_remaining", 0)) > 0
                and expires_at > now
            ):
                continue
            owner_agent_id = str(intent["owner_agent_id"])
            self.discovered_intents[intent_id] = owner_agent_id
            matches.append(
                {
                    "intent_id": intent_id,
                    "owner_agent_id": owner_agent_id,
                    "intent_type": intent["intent_type"],
                    "public_title": intent["public_title"],
                    "public_summary": intent["public_summary"],
                    "public_constraints": constraints,
                    "public_requirements": intent.get("public_requirements", []),
                    "capacity_remaining": int(intent["capacity_remaining"]),
                    "expires_at": intent["expires_at"],
                    "status": intent["status"],
                }
            )
        result = {
            "open_intents": matches,
            "private_profiles_read": False,
            "owner_only_fields_read": False,
        }
        return await self._observe(
            tool="search_open_intents",
            started=started,
            arguments={"intent_type": intent_type, "location": location},
            result=result,
            transition="open_intents_discovered",
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
                from_intent_id=self.source_intent_id,
                to_intent_id=self.source_intent_id,
            )
        introduced = [
            str(claim.value)
            for claim in result.response.claims
            if claim.field == "introduced_agent_id"
        ]
        introduced_intents = [
            str(claim.value)
            for claim in result.response.claims
            if claim.field == "introduced_intent_id"
        ]
        if len(introduced) != len(introduced_intents):
            raise ValueError("introduction must bind an agent to an active intent")
        for agent_id, intent_id in zip(introduced, introduced_intents, strict=True):
            intent = await self.store.get("intents", intent_id)
            if (
                intent is None
                or intent.get("owner_agent_id") != agent_id
                or intent.get("status") != IntentStatus.OPEN.value
                or int(intent.get("capacity_remaining", 0)) < 1
            ):
                raise ValueError("introduced intent is not currently contactable")
            self.warm_introduced_intents[intent_id] = agent_id
        await self._persist_exchange(result.request, route="warm_introduction_request")
        await self._persist_exchange(
            result.response, route="warm_introduction_response"
        )
        output = {
            "peer": result.response.from_agent_id,
            "speech_act": result.response.speech_act.value,
            "natural_language": result.response.natural_language,
            "introduced_agent_ids": introduced,
            "introduced_intent_ids": introduced_intents,
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

    async def contact_candidates(
        self, target_intent_ids: list[str], question: str
    ) -> dict[str, Any]:
        """Ask owners of one or two model-selected posts a scoped question."""

        started = self._before_tool()
        if not 1 <= len(target_intent_ids) <= self.MAX_ACTIVE_CANDIDATES:
            raise ValueError("contact one or two intent posts per bounded batch")
        if len(set(target_intent_ids)) != len(target_intent_ids):
            raise ValueError("intent batch contains a duplicate post")
        eligible = self.discovered_intents | self.warm_introduced_intents
        if any(intent_id not in eligible for intent_id in target_intent_ids):
            raise ValueError("intent is neither publicly discovered nor introduced")
        new_intents = set(target_intent_ids) - self.contacted_intents
        if len(self.contacted_intents | new_intents) > self.MAX_ACTIVE_CANDIDATES:
            raise ValueError("maximum active intent negotiations reached")
        if any(
            self.message_counts.get(
                canonical_intent_pair(self.source_intent_id, target_intent_id), 0
            )
            >= self.MAX_MESSAGES_PER_PAIR
            for target_intent_id in target_intent_ids
        ):
            raise ValueError("maximum messages for an intent pair reached")
        safe_question = self.privacy.validate(natural_language=question, references=[])
        results = await asyncio.gather(
            *(
                self._contact_candidate(target_intent_id, safe_question)
                for target_intent_id in target_intent_ids
            )
        )
        output = {"candidate_responses": list(results)}
        return await self._observe(
            tool="contact_candidates",
            started=started,
            arguments={
                "target_intent_ids": target_intent_ids,
                "question": safe_question,
            },
            result=output,
            transition="candidate_claims_recorded_as_beliefs",
        )

    async def _contact_candidate(
        self, target_intent_id: str, safe_question: str
    ) -> dict[str, Any]:
        """Run one member of a prevalidated, bounded candidate contact batch."""

        eligible = self.discovered_intents | self.warm_introduced_intents
        if target_intent_id not in eligible:
            raise ValueError("intent is neither publicly discovered nor introduced")
        candidate_agent_id = eligible[target_intent_id]
        if (
            target_intent_id not in self.contacted_intents
            and len(self.contacted_intents) >= self.MAX_ACTIVE_CANDIDATES
        ):
            raise ValueError("maximum active intent negotiations reached")
        pair_session_id = canonical_intent_pair(self.source_intent_id, target_intent_id)
        count = self.message_counts.get(pair_session_id, 0)
        if count >= self.MAX_MESSAGES_PER_PAIR:
            raise ValueError("maximum messages for this agent pair reached")
        async with self._peer_semaphore:
            result = await request_peer_agent(
                peer_base_url=self.peer_base_url,
                to_agent_id=candidate_agent_id,
                speech_act=SpeechAct.INFORMATION_REQUEST,
                natural_language=safe_question,
                run_id=self.run_id,
                session_id=self.session_id,
                from_intent_id=self.source_intent_id,
                to_intent_id=target_intent_id,
                pair_session_id=pair_session_id,
            )
        self.contacted_intents.add(target_intent_id)
        self.message_counts[pair_session_id] = count + 1
        await self.store.upsert(
            "intent_pair_sessions",
            pair_session_id,
            {
                "pair_session_id": pair_session_id,
                "source_intent_id": self.source_intent_id,
                "target_intent_id": target_intent_id,
                "source_agent_id": "qi-agent",
                "target_agent_id": candidate_agent_id,
                "runId": str(self.run_id),
                "status": "ACTIVE",
                "updated_at": datetime.now(UTC),
            },
        )
        await self._persist_exchange(result.request, route="candidate_inquiry_request")
        await self._persist_exchange(
            result.response, route="candidate_inquiry_response"
        )
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
            self.beliefs.setdefault(target_intent_id, {})[claim.field] = evidence
            belief_id = sha256(
                f"{self.run_id}:{candidate_agent_id}:{claim.field}".encode()
            ).hexdigest()
            await self.store.upsert(
                "beliefs",
                belief_id,
                {
                    **evidence.model_dump(mode="json"),
                    "runId": str(self.run_id),
                    "sourceIntentId": self.source_intent_id,
                    "targetIntentId": target_intent_id,
                    "pairSessionId": pair_session_id,
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
            "target_intent_id": target_intent_id,
            "pair_session_id": pair_session_id,
            "speech_act": result.response.speech_act.value,
            "natural_language": result.response.natural_language,
            "claims": claims,
            "message_id": str(result.response.message_id),
            "retry_count": result.retry_count,
        }
        return output

    async def record_candidate_disposition(
        self,
        target_intent_id: str,
        disposition: Literal["CONTINUE", "DEPRIORITIZE", "WITHDRAW"],
        observable_reason: str,
    ) -> dict[str, Any]:
        """Record Qi's evidence-based continue, deprioritize, or withdraw decision."""

        started = self._before_tool()
        eligible = self.discovered_intents | self.warm_introduced_intents
        candidate_agent_id = eligible.get(target_intent_id)
        if candidate_agent_id is None:
            raise ValueError("target intent was not discovered")
        if target_intent_id not in self.beliefs:
            raise ValueError("candidate has no received evidence")
        self.dispositions[target_intent_id] = disposition
        disposition_id = sha256(
            f"{self.run_id}:{target_intent_id}:disposition".encode()
        ).hexdigest()
        await self.store.upsert(
            "beliefs",
            disposition_id,
            {
                "runId": str(self.run_id),
                "subjectAgentId": candidate_agent_id,
                "targetIntentId": target_intent_id,
                "field": "qi_disposition",
                "value": disposition,
                "kind": EvidenceKind.MODEL_INFERENCE.value,
                "observableReason": observable_reason,
                "authoritativeFact": False,
            },
        )
        output = {
            "candidate_agent_id": candidate_agent_id,
            "target_intent_id": target_intent_id,
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
        self, target_intent_id: str
    ) -> dict[str, Any]:
        """Calculate partial-overlap cost from authoritative availability."""

        started = self._before_tool()
        target_intent = await self.store.get("intents", target_intent_id)
        if (
            target_intent is None
            or target_intent.get("status") != IntentStatus.OPEN.value
        ):
            raise ValueError("target intent is no longer OPEN")
        candidate_agent_id = str(target_intent["owner_agent_id"])
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
        target_constraints = dict(target_intent["public_constraints"])
        target_start = date.fromisoformat(str(target_constraints["date_start"]))
        target_end = date.fromisoformat(str(target_constraints["date_end"]))
        shared_start = max(self.goal_start, availability.start, target_start)
        shared_end = min(self.goal_end, availability.end, target_end)
        shared_nights = max(0, (shared_end - shared_start).days)
        total_nights = (self.goal_end - self.goal_start).days
        additional = calculate_additional_cost(
            total_nights=total_nights,
            shared_nights=shared_nights,
            nightly_room_cost_usd=self.ROOM_RATE_USD,
        )
        output = {
            "candidate_agent_id": candidate_agent_id,
            "target_intent_id": target_intent_id,
            "total_nights": total_nights,
            "shared_nights": shared_nights,
            "shared_start": shared_start.isoformat(),
            "shared_end": shared_end.isoformat(),
            "nightly_room_cost_usd": self.ROOM_RATE_USD,
            "additional_cost_usd": additional,
            "delegated_maximum_usd": self.delegated_maximum_usd,
            "within_delegated_authority": additional <= self.delegated_maximum_usd,
            "availability_version": availability.version,
        }
        return await self._observe(
            tool="calculate_candidate_plan_cost",
            started=started,
            arguments={"target_intent_id": target_intent_id},
            result=output,
            transition="deterministic_cost_calculated",
        )

    async def create_proposal(
        self,
        target_intent_id: str,
        shared_start: str,
        shared_end: str,
        solo_dates: list[str],
    ) -> dict[str, Any]:
        """Create a versioned proposal only within verified delegated authority."""

        started = self._before_tool()
        target_intent = await self.store.get("intents", target_intent_id)
        if target_intent is None:
            raise ValueError("target intent no longer exists")
        eligible = self.discovered_intents | self.warm_introduced_intents
        candidate_agent_id = eligible.get(target_intent_id)
        if candidate_agent_id is None:
            raise ValueError("target intent was not discovered")
        if self.dispositions.get(target_intent_id) in {"DEPRIORITIZE", "WITHDRAW"}:
            raise ValueError("candidate negotiation is not active")
        if target_intent_id not in self.beliefs:
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
        total_nights = (self.goal_end - self.goal_start).days
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
            source_intent_id=self.source_intent_id,
            target_intent_id=target_intent_id,
            pair_session_id=canonical_intent_pair(
                self.source_intent_id, target_intent_id
            ),
            candidate_agent_id=candidate_agent_id,
            version=1,
            shared_start=parsed_start,
            shared_end=parsed_end,
            solo_dates=[date.fromisoformat(item) for item in solo_dates],
            additional_cost_usd=additional,
            delegated_maximum_usd=self.delegated_maximum_usd,
            terms=[
                "Qi stays alone on each solo date.",
                "Qi and the candidate share on the shared dates.",
                "The shared nights are split equally.",
            ],
            disclosure_hash=disclosure_hash(disclosures),
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        self.authority.add_proposal(proposal)
        self.proposals[proposal.proposal_id] = proposal
        payload = {
            **proposal.model_dump(mode="json"),
            "runId": str(self.run_id),
            "status": "PROPOSED",
            "availabilityVersion": availability.version,
            "disclosures": disclosures,
            "introductionUsed": target_intent_id in self.warm_introduced_intents,
            "introducedThroughAgentId": (
                "alice-agent"
                if target_intent_id in self.warm_introduced_intents
                else None
            ),
        }
        await self.store.create("proposals", str(proposal.proposal_id), payload)
        await self.store.create(
            "proposal_versions",
            f"{proposal.proposal_id}-v{proposal.version}",
            payload,
        )
        for intent_id, document in (
            (
                self.source_intent_id,
                await self.store.get("intents", self.source_intent_id),
            ),
            (target_intent_id, target_intent),
        ):
            if document is None:
                raise ValueError("proposal intent disappeared")
            document.pop("_updateTime", None)
            document["status"] = IntentStatus.NEGOTIATING.value
            document["active_run_id"] = str(self.run_id)
            document["active_pair_session_id"] = proposal.pair_session_id
            await self.store.upsert("intents", intent_id, document)
        await self._event(
            "proposal.created",
            {
                "proposalId": str(proposal.proposal_id),
                "version": proposal.version,
            },
            f"{self.run_id}:proposal:{proposal.proposal_id}:v{proposal.version}",
            publish_immediately=False,
        )
        output = {
            "proposal_id": str(proposal.proposal_id),
            "version": proposal.version,
            "candidate_agent_id": candidate_agent_id,
            "source_intent_id": self.source_intent_id,
            "target_intent_id": target_intent_id,
            "pair_session_id": proposal.pair_session_id,
            "shared_start": shared_start,
            "shared_end": shared_end,
            "solo_dates": solo_dates,
            "additional_cost_usd": additional,
            "delegated_maximum_usd": self.delegated_maximum_usd,
            "expires_at": proposal.expires_at.isoformat(),
        }
        return await self._observe(
            tool="create_proposal",
            started=started,
            arguments={
                "target_intent_id": target_intent_id,
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
                from_intent_id=self.source_intent_id,
                to_intent_id=str(proposal.target_intent_id),
                pair_session_id=str(proposal.pair_session_id),
                proposal=A2AProposal(
                    version=proposal.version,
                    shared_start=proposal.shared_start,
                    shared_end=proposal.shared_end,
                    solo_dates=proposal.solo_dates,
                    additional_cost_usd=proposal.additional_cost_usd,
                    cost_rule="equal_split_shared_nights",
                ),
            )
        await self._persist_exchange(result.request, route="proposal_request")
        await self._persist_exchange(result.response, route="proposal_response")
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

    async def place_soft_hold_and_request_user_approval(
        self,
        proposal_id: str,
        recommendation: str,
        remaining_uncertainty: str,
    ) -> dict[str, Any]:
        """Place a hold and pause at the effect contract after both agents accept."""

        started = self._before_tool()
        proposal = self.proposals[UUID(proposal_id)]
        accepted = self.authority.acceptances.get(
            (proposal.proposal_id, proposal.version), set()
        )
        if accepted != {"qi-agent", proposal.candidate_agent_id}:
            raise ValueError("both personal agents must accept before a hold")
        hold = self.authority.place_hold(
            proposal.proposal_id, expires_at=datetime.now(UTC) + timedelta(minutes=15)
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
            publish_immediately=False,
        )
        hold_output = {
            "hold_id": str(hold.hold_id),
            "proposal_id": proposal_id,
            "proposal_version": proposal.version,
            "source_intent_id": proposal.source_intent_id,
            "target_intent_id": proposal.target_intent_id,
            "pair_session_id": proposal.pair_session_id,
            "capacity_reserved": hold.capacity_reserved,
            "status": hold.status,
            "idempotency_key": hold.idempotency_key,
            "expires_at": hold.expires_at.isoformat(),
            "active": hold.active,
        }
        return await self._request_user_approval(
            proposal_id=proposal_id,
            recommendation=recommendation,
            remaining_uncertainty=remaining_uncertainty,
            started=started,
            hold_output=hold_output,
        )

    async def _request_user_approval(
        self,
        *,
        proposal_id: str,
        recommendation: str,
        remaining_uncertainty: str,
        started: float,
        hold_output: dict[str, Any],
    ) -> dict[str, Any]:
        """Pause at a complete effect contract; never approve on the user's behalf."""

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
            "sourceIntentId": proposal.source_intent_id,
            "targetIntentId": proposal.target_intent_id,
            "pairSessionId": proposal.pair_session_id,
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
        for intent_id in (proposal.source_intent_id, proposal.target_intent_id):
            if intent_id is None:
                raise ValueError("approval requires intent-scoped proposal")
            intent = await self.store.get("intents", intent_id)
            if intent is None:
                raise ValueError("approval intent disappeared")
            intent.pop("_updateTime", None)
            intent.update(
                status=IntentStatus.AWAITING_APPROVAL.value,
                active_hold_id=str(hold.hold_id),
                active_pair_session_id=proposal.pair_session_id,
            )
            await self.store.upsert("intents", intent_id, intent)
        self.boundary_elapsed_ms = int((perf_counter() - self.started_at) * 1000)
        await self.store.upsert(
            "runs",
            str(self.run_id),
            {
                "runId": str(self.run_id),
                "goalId": str(self.goal_id),
                "sourceIntentId": self.source_intent_id,
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
            publish_immediately=False,
        )
        output = {
            "status": self.status,
            "hold": hold_output,
            "effect_contract": contract,
        }
        return await self._observe(
            tool="place_soft_hold_and_request_user_approval",
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
        await self.release_run_negotiations(reason="safe_no_match")
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

    async def release_run_negotiations(self, *, reason: str) -> None:
        """Release only this run's uncommitted intent capacity and sessions."""

        now = datetime.now(UTC)
        for intent in await self.store.list_documents("intents"):
            if intent.get("active_run_id") != str(self.run_id):
                continue
            if intent.get("status") not in {
                IntentStatus.NEGOTIATING.value,
                IntentStatus.HELD.value,
            }:
                continue
            intent_id = str(intent.get("intent_id") or intent.get("_id"))
            intent.pop("_updateTime", None)
            intent.pop("_id", None)
            intent.pop("active_run_id", None)
            intent.pop("active_pair_session_id", None)
            intent.pop("active_hold_id", None)
            intent["status"] = IntentStatus.OPEN.value
            intent["released_at"] = now
            intent["release_reason"] = reason
            await self.store.upsert("intents", intent_id, intent)
        for session in await self.store.list_documents("intent_pair_sessions"):
            current_status = session.get("status")
            if (
                session.get("runId") != str(self.run_id)
                or current_status not in {"ACTIVE", "PROPOSED", "HELD"}
            ):
                continue
            session_id = str(session.get("pair_session_id") or session.get("_id"))
            session.pop("_updateTime", None)
            session.pop("_id", None)
            session.update(
                status="RELEASED", released_at=now, release_reason=reason
            )
            await self.store.upsert("intent_pair_sessions", session_id, session)
        for hold in await self.store.list_documents("holds"):
            if hold.get("runId") != str(self.run_id) or hold.get("active") is not True:
                continue
            hold_id = str(hold.get("hold_id") or hold.get("_id"))
            hold.pop("_updateTime", None)
            hold.pop("_id", None)
            hold.update(
                active=False,
                status="RELEASED",
                releasedAt=now,
                releaseReason=reason,
            )
            await self.store.upsert("holds", hold_id, hold)

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
                "fromIntentId": envelope.from_intent_id,
                "toIntentId": envelope.to_intent_id,
                "pairSessionId": envelope.pair_session_id,
            },
            f"{self.run_id}:message.received:{envelope.message_id}",
            publish_immediately=False,
        )
