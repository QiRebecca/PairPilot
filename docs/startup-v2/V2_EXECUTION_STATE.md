# Startup V2 execution state

Updated: 2026-09-01

## Current phase

Phase 11 — Closed-beta acceptance: `PARTIAL`

The isolated candidate is live at revision `pairpilot-orchestrator-00053-suw`
with zero production traffic. Ten independently authenticated controlled users,
three Communities, 25 Requests/Posts, all five task types, 20 mixed-state Memories,
eight real Agent contacts, seven dual-approved Matches, four completions and three
cancellations passed through generic runtime and authoritative APIs. A separate
80-request/20-concurrency authenticated smoke passed with zero failures. The same
global Personal Agent conversation completed live draft, revise and explicit publish
turns after a 429 recovery defect was reproduced and fixed. Phase 11 remains partial
because the full ten-scenario matrix, offline monitoring, failure injection, and
authenticated visual/accessibility acceptance have not all passed.

## Protected baselines

- Git: `hackathon-submission-final` → `7d3d6f6f4b830688e7d522c2a9517cf8833d27ae`
- Submitted Cloud Run: `pairpilot-orchestrator-00045-tig`
- Current production: `pairpilot-orchestrator-00050-qiq`
- Current model: `gemini-3.7-flash`
- Startup branch: `startup-v2`

## Phase status

| Phase | Status | Next authoritative gate |
|---|---|---|
| 0 Audit and protection | IMPLEMENTED_UNVERIFIED | Candidate environment gate required for LIVE_VERIFIED |
| 1 Unified domain model | PARTIAL | Remaining lifecycle migrations and candidate apply |
| 2 Explore and Post Detail | PARTIAL | Vector index/backfill, monitoring worker, candidate acceptance |
| 3 Communities | PARTIAL | moderation actions, cross-path rule enforcement, candidate acceptance |
| 4 Rooms | PARTIAL | shared Agent draft/approve/send and complete state-transition acceptance |
| 5 Matches | PARTIAL | calendar/contact/change/reapproval/backup and failure-injection acceptance |
| 6 Connections | PARTIAL | candidate relationship-reuse and browser acceptance |
| 7 Memory | PARTIAL | candidate semantic scope and browser acceptance |
| 8 Product glue | PARTIAL | remaining inline decisions, all-action runtime enforcement, candidate acceptance |
| 9 Safety and operations | PARTIAL | candidate moderation/DLQ/failure acceptance and provider metrics |
| 10 Unified UI refinement | PARTIAL | remaining route decomposition and authenticated four-viewport visual/a11y QA |
| 11 Closed-beta acceptance | PARTIAL | run remaining live/security/offline/reliability and visual scenarios |
| 12 Deployment/promotion | PARTIAL | candidate is deployed and traced; migration apply and production promotion remain gated |

## Immediate next work

1. Run the ten named lifecycle scenarios that are not covered by the core cohort run.
2. Run duplicate delivery, DLQ, lease expiry, conflict, expiry, orphan and reconnect
   failure injection in the isolated candidate.
3. Apply the versioned migration only to `candidate_v2_` after its dry-run gate.
4. Run authenticated four-viewport visual/accessibility acceptance.
5. Keep production traffic and production migration apply unchanged until every gate
   passes.

## Known blockers

- Production contains mixed legacy and V1 state vocabularies.
- Twenty-six scanned historical records require explicit environment classification.
- The DLQ inspection subscription has 25 undelivered messages requiring
  classification; the production push worker itself has zero backlog.
- Firestore has no composite indexes for the planned search filters.
- Firestore has no candidate vector index or public-Post embedding backfill.
- Saved-search events are durable but no V2 monitoring worker consumes them yet.
- Core authenticated pages still remaining in `BetaApp.tsx` need decomposition.
- Agent-drafted shared Room messages still need an explicit draft/approve/send path.
- Authenticated V2 four-viewport screenshots and keyboard/screen-reader QA have not run.
- Candidate offline monitoring, failure injection and browser-level acceptance are
  not yet V2-verified.
