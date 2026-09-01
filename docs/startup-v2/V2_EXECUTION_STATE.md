# Startup V2 execution state

Updated: 2026-09-01

## Current phase

Phase 3 — Communities: `PARTIAL`

Operational Community Detail, five scoped tabs, membership-policy enforcement,
public member/Agent projections, Community-visible Room filtering, and a
privacy-bounded logical Community Agent exist. Local authenticated browser
acceptance exposed and fixed slow member reads, blank empty states, and
controlled-test directory leakage. Phase 3 remains partial until moderation
actions, rule enforcement at every publish/contact path, candidate deployment,
and multi-user acceptance pass.

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
| 4 Rooms | PARTIAL | V2 lifecycle, summary, three-channel acceptance |
| 5 Matches | PARTIAL | plan detail/change/cancel/calendar/backup |
| 6 Connections | PARTIAL | list/detail/provenance/reuse acceptance |
| 7 Memory | PARTIAL | types, scope, usage events, contradiction handling |
| 8 Product glue | PARTIAL | Decision Inbox, notification actions, autonomy policies |
| 9 Safety and operations | PARTIAL | moderation, DLQ operations, analytics, operational Admin |
| 10 Unified UI refinement | NOT_IMPLEMENTED | decomposed routes and four-viewport visual QA |
| 11 Closed-beta acceptance | NOT_IMPLEMENTED | ten controlled users and all ten scenarios |
| 12 Deployment/promotion | NOT_IMPLEMENTED | no-traffic V2 candidate and migration gates |

## Immediate next work

1. Build V2 Room state, summary, and three strictly separated channels.
2. Implement the remaining lifecycle normalization migrations.
3. Add candidate-environment feature and namespace configuration.
4. Create candidate vector index and public-Post embedding backfill.
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
