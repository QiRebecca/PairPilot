# Startup V2 execution state

Updated: 2026-09-01

## Current phase

Phase 1 — Unified domain model: `PARTIAL`

Canonical lifecycle contracts, server-side Post transition enforcement, the
versioned migration registry, environment/backup/write guards, paginated scanning,
and the first privacy-safe production dry-run exist. Phase 1 remains partial
until legacy Room, Match, Connection, Decision, Notification, Memory, and
Autonomy records are normalized in an isolated candidate environment.

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

1. Implement the remaining lifecycle normalization migrations.
2. Add candidate-environment feature and namespace configuration.
3. Normalize public API projections behind versioned V2 contracts.
4. Build server-side Explore search, saved searches, and Post Detail.
5. Keep production migration apply disabled until backup and candidate gates pass.

## Known blockers

- Production contains mixed legacy and V1 state vocabularies.
- Twenty-six scanned historical records require explicit environment classification.
- Candidate Pub/Sub isolation is absent.
- The DLQ inspection subscription has 25 undelivered messages requiring
  classification; the production push worker itself has zero backlog.
- Firestore has no composite indexes for the planned search filters.
- The frontend is concentrated in `BetaApp.tsx`.
- Offline monitoring and browser-level acceptance are not yet V2-verified.
