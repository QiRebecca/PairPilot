# Startup V2 execution state

Updated: 2026-09-01

## Current phase

Phase 11 — Closed-beta acceptance: `PARTIAL`

Candidate state now has a fail-closed physical collection prefix and independent
Pub/Sub topology definition. A ten-user/three-Community/25-Post seeder and bounded
acceptance driver exist and pass local static/unit gates. The driver uses generic
Agent and authoritative lifecycle routes rather than writing outcomes directly.
Phase 11 remains partial because no candidate revision is deployed, no cohort is
seeded, and no live multi-user scenario has yet passed against Startup V2.

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
| 4 Rooms | PARTIAL | live private-Agent turn, draft/approve/send, candidate acceptance |
| 5 Matches | PARTIAL | candidate multi-user and failure-injection acceptance |
| 6 Connections | PARTIAL | candidate relationship-reuse and browser acceptance |
| 7 Memory | PARTIAL | candidate semantic scope and browser acceptance |
| 8 Product glue | PARTIAL | remaining inline decisions, all-action runtime enforcement, candidate acceptance |
| 9 Safety and operations | PARTIAL | candidate moderation/DLQ/failure acceptance and provider metrics |
| 10 Unified UI refinement | PARTIAL | remaining route decomposition and authenticated four-viewport visual/a11y QA |
| 11 Closed-beta acceptance | PARTIAL | deploy isolated candidate, seed cohort, run all live/security/reliability scenarios |
| 12 Deployment/promotion | NOT_IMPLEMENTED | no-traffic V2 candidate and migration gates |

## Immediate next work

1. Commit the candidate-isolation and cohort tooling checkpoint.
2. Deploy an immutable no-traffic candidate and verify its health/environment.
3. Seed the ten-user, three-Community cohort and run bounded acceptance.
4. Run remaining failure injection and authenticated visual/accessibility gates.
5. Keep production traffic and migration apply unchanged until every gate passes.

## Known blockers

- Production contains mixed legacy and V1 state vocabularies.
- Twenty-six scanned historical records require explicit environment classification.
- Candidate Pub/Sub isolation is implemented in deployment tooling but not deployed.
- The DLQ inspection subscription has 25 undelivered messages requiring
  classification; the production push worker itself has zero backlog.
- Firestore has no composite indexes for the planned search filters.
- Firestore has no candidate vector index or public-Post embedding backfill.
- Saved-search events are durable but no V2 monitoring worker consumes them yet.
- Core authenticated pages still remaining in `BetaApp.tsx` need decomposition.
- Agent-drafted shared Room messages still need an explicit draft/approve/send path.
- Authenticated V2 four-viewport screenshots and keyboard/screen-reader QA have not run.
- Offline monitoring and browser-level acceptance are not yet V2-verified.
