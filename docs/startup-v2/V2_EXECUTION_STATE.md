# Startup V2 execution state

Updated: 2026-09-01

## Current phase

Phase 10 — Unified UI refinement: `PARTIAL`

The Request route is now a seven-tab workspace with Conversation as the default,
the persistent Personal Agent remains the single chat surface, and Room-private
Agent communication invokes that same live task-scoped conversation. Responsive
Request/Admin layouts, reduced-motion support, explicit offline state, semantic
controls, and route-level Operations were added. Phase 10 remains partial until
all core routes are decomposed and the authenticated four-viewport visual,
keyboard, screen-reader, and recovery-state matrix passes in a candidate.

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
| 11 Closed-beta acceptance | NOT_IMPLEMENTED | ten controlled users and all ten scenarios |
| 12 Deployment/promotion | NOT_IMPLEMENTED | no-traffic V2 candidate and migration gates |

## Immediate next work

1. Create an isolated candidate namespace before controlled-cohort acceptance.
2. Build the ten-user, three-Community controlled cohort without hardcoded outcomes.
3. Run security, offline monitoring, failure, concurrency, and performance scenarios.
4. Capture the authenticated four-viewport visual and accessibility matrix.
5. Keep production migration apply disabled until backup and candidate gates pass.

## Known blockers

- Production contains mixed legacy and V1 state vocabularies.
- Twenty-six scanned historical records require explicit environment classification.
- Candidate Pub/Sub isolation is absent.
- The DLQ inspection subscription has 25 undelivered messages requiring
  classification; the production push worker itself has zero backlog.
- Firestore has no composite indexes for the planned search filters.
- Firestore has no candidate vector index or public-Post embedding backfill.
- Saved-search events are durable but no V2 monitoring worker consumes them yet.
- Core authenticated pages still remaining in `BetaApp.tsx` need decomposition.
- Agent-drafted shared Room messages still need an explicit draft/approve/send path.
- Authenticated V2 four-viewport screenshots and keyboard/screen-reader QA have not run.
- Offline monitoring and browser-level acceptance are not yet V2-verified.
