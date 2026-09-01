# Startup V2 execution state

Updated: 2026-09-01

## Current phase

Phase 0 — Audit and protection: `IMPLEMENTED_UNVERIFIED`

The submission snapshot, rollback revision, V2 branch, baseline inventory, gap
matrix, and migration plan exist. Phase 0 becomes `LIVE_VERIFIED` only after the
new audit artifacts pass repository checks and the privacy-safe inventory is rerun
successfully from the clean V2 branch.

## Protected baselines

- Git: `hackathon-submission-final` → `7d3d6f6f4b830688e7d522c2a9517cf8833d27ae`
- Submitted Cloud Run: `pairpilot-orchestrator-00045-tig`
- Current production: `pairpilot-orchestrator-00050-qiq`
- Current model: `gemini-3.7-flash`
- Startup branch: `startup-v2`

## Phase status

| Phase | Status | Next authoritative gate |
|---|---|---|
| 0 Audit and protection | IMPLEMENTED_UNVERIFIED | Clean tests, inventory rerun, audit commit |
| 1 Unified domain model | PARTIAL | V2 state validators and dry-run migration framework |
| 2 Explore and Post Detail | PARTIAL | Server search contract and direct Post route |
| 3 Communities | PARTIAL | Community Detail/rules/roles/Community Agent |
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

1. Implement schema migration registry and dry-run runner.
2. Add V2 enums and server-side transition validators without changing production.
3. Add candidate-environment feature and namespace configuration.
4. Normalize public API projections behind versioned V2 contracts.
5. Begin Explore/Post Detail only after the domain gates pass.

## Known blockers

- Production contains mixed legacy and V1 state vocabularies.
- Candidate Pub/Sub isolation is absent.
- The DLQ inspection subscription has 25 undelivered messages requiring
  classification; the production push worker itself has zero backlog.
- Firestore has no composite indexes for the planned search filters.
- The frontend is concentrated in `BetaApp.tsx`.
- Offline monitoring and browser-level acceptance are not yet V2-verified.
