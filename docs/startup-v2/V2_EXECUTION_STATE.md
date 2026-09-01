# Startup V2 execution state

Updated: 2026-09-01

## Current phase

Phase 5 — Matches: `PARTIAL`

Participant-scoped Match list/detail read models, canonical time-aware states,
calendar export, dual-approved material changes, audited cancellation, backup
activation, opt-in Contact Cards, explicit completion, private outcome, and
safety signaling now exist locally. Phase 5 remains partial until candidate
multi-user browser acceptance and concurrency/failure-injection gates pass.

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
| 6 Connections | PARTIAL | list/detail/provenance/reuse acceptance |
| 7 Memory | PARTIAL | types, scope, usage events, contradiction handling |
| 8 Product glue | PARTIAL | Decision Inbox, notification actions, autonomy policies |
| 9 Safety and operations | PARTIAL | moderation, DLQ operations, analytics, operational Admin |
| 10 Unified UI refinement | NOT_IMPLEMENTED | decomposed routes and four-viewport visual QA |
| 11 Closed-beta acceptance | NOT_IMPLEMENTED | ten controlled users and all ten scenarios |
| 12 Deployment/promotion | NOT_IMPLEMENTED | no-traffic V2 candidate and migration gates |

## Immediate next work

1. Build Connection list/detail, provenance, and warm-reuse flows.
2. Connect private Room instructions to live Personal Agent turns and shared drafts.
3. Implement the remaining lifecycle normalization migrations.
4. Add candidate-environment feature and namespace configuration.
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
- Offline monitoring and browser-level acceptance are not yet V2-verified.
