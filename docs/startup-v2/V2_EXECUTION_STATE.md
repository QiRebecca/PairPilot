# Startup V2 execution state

Updated: 2026-09-08

## Current phase

Phase 11 — Closed-beta acceptance: `PARTIAL`

The isolated candidate is live at revision `pairpilot-orchestrator-00071-gaq`
(`sha256:c3cf489681873310fc1e91823a4a5554d50f726d7ff7ad936a378e94d9c638ff`)
with zero production traffic. Ten independently authenticated controlled users,
three Communities, 66 Requests, 61 Posts and all five task types are present. The
latest 80-request/20-concurrency authenticated smoke passed with zero failures and
the same global Personal Agent conversation completed live draft, revise and
explicit publish turns. The candidate migration is applied and a post-runtime
scan of 1,735 documents reports zero drift. Additional live matrices pass Room
isolation, Community scope, exact-version dual approval, Match change/calendar,
Contact Cards, Memory controls, notifications and action-specific autonomy.

A separate authenticated browser journey for a real owner account also completed
Post publication, compatible-candidate contact, two-Agent negotiation, proposal,
independent approvals, committed Match, two-human Shared Room messages, Connection
creation and Memory confirmation. Phase 11 remains partial because the full
failure-injection matrix, four-viewport accessibility acceptance and provider soak
window have not all passed.

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
| 1 Unified domain model | PARTIAL | Candidate is converged; production migration remains gated |
| 2 Explore and Post Detail | PARTIAL | Vector index/backfill and authenticated multi-viewport acceptance |
| 3 Communities | PARTIAL | moderation actions, cross-path rule enforcement, candidate acceptance |
| 4 Rooms | PARTIAL | Core channels are live-verified; shared Agent draft/approve/send remains |
| 5 Matches | PARTIAL | Authenticated browser passed; failure-injection acceptance remains |
| 6 Connections | LIVE_VERIFIED | Real owner account and controlled peer produced an inspectable Connection |
| 7 Memory | LIVE_VERIFIED | Real owner confirmation and scoped lifecycle matrices passed |
| 8 Product glue | PARTIAL | remaining inline decisions, all-action runtime enforcement, candidate acceptance |
| 9 Safety and operations | PARTIAL | candidate moderation/DLQ/failure acceptance and provider metrics |
| 10 Unified UI refinement | PARTIAL | remaining route decomposition and authenticated four-viewport visual/a11y QA |
| 11 Closed-beta acceptance | PARTIAL | run remaining live/security/offline/reliability and visual scenarios |
| 12 Deployment/promotion | PARTIAL | candidate migration/deploy are verified; production backup, migration and promotion remain gated |

## Immediate next work

1. Run duplicate delivery, DLQ, lease expiry, conflict, expiry, orphan and reconnect
   failure injection in the isolated candidate.
2. Run authenticated four-viewport visual/accessibility acceptance.
3. Complete a provider-capacity soak and alerting gate.
4. Export a production backup, re-run the production migration plan and only then
   consider promotion. Keep production traffic unchanged until every gate passes.

## Known blockers

- Production contains mixed legacy and V1 state vocabularies.
- Production migration still requires a fresh reviewed plan and export backup.
- The DLQ inspection subscription has 25 undelivered messages requiring
  classification; the production push worker itself has zero backlog.
- Firestore has no composite indexes for the planned search filters.
- Firestore has no candidate vector index or public-Post embedding backfill.
- Agent-drafted shared Room messages still need an explicit draft/approve/send path.
- Authenticated V2 four-viewport screenshots and keyboard/screen-reader QA have not run.
- Candidate failure injection is not yet V2-verified; authenticated desktop browser
  acceptance has passed for the primary owner journey.
- Vertex AI returned transient 429 responses during the context matrix; bounded SDK
  retries recovered and all nine Agent turns completed, but provider-capacity alerts
  and a longer soak window remain required before public launch.
