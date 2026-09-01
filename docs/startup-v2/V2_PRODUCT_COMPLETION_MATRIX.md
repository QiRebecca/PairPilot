# Startup V2 product completion matrix

Updated: 2026-09-01

Only `NOT_IMPLEMENTED`, `PARTIAL`, `IMPLEMENTED_UNVERIFIED`, and `LIVE_VERIFIED`
are valid completion states.

| Capability | Status | Current evidence / missing gate |
|---|---|---|
| Submission snapshot and rollback | LIVE_VERIFIED | Git tag, submitted revision, digest, rollback command recorded |
| Persistent Personal Agent multi-turn chat | LIVE_VERIFIED | Production real-Gemini two-turn and multi-user acceptance |
| Authenticated multi-user isolation | LIVE_VERIFIED | Firebase principals, owner checks, deny-all Firestore browser rules, tests |
| Unified V2 schema and state machines | PARTIAL | Canonical Post, Room, Match, Connection, Memory, Decision, Notification, and action-autonomy vocabularies plus validators exist; legacy Room/Match/Connection runtime writes still need migration |
| Versioned migration framework | IMPLEMENTED_UNVERIFIED | Registry, checksums, pagination, dry-run, optimistic concurrency, environment/backup guards, migration report, and real 3,093-record dry-run pass; candidate apply is still gated |
| Request workspace tabs and activity | PARTIAL | Request route works; required tabbed workspace and material-change invalidation missing |
| Explore natural-language and structured search | PARTIAL | Authenticated server filters, six views, bounded text relevance, result explanations, and local browser acceptance pass; Firestore vector index and embedding backfill remain gated |
| Saved Posts and saved searches | PARTIAL | Owner-scoped entities, save/remove APIs, monitored-search event, and UI exist; event worker monitoring and candidate acceptance remain |
| Post Detail route | IMPLEMENTED_UNVERIFIED | Authorized `/app/posts/:intentId` and public-only API pass local browser direct-link acceptance; candidate deployment remains |
| Agent evaluate/contact from Post | IMPLEMENTED_UNVERIFIED | Post Detail selects an owned compatible Request and invokes real candidate processing; candidate multi-user acceptance remains |
| Community join/leave | LIVE_VERIFIED | Authenticated APIs and production data exist |
| Community Detail and scoped feed | IMPLEMENTED_UNVERIFIED | Direct route, five tabs, scoped Posts/members/Rooms pass local tests and browser acceptance |
| Community rules and moderation | PARTIAL | Rules are visible and Agent-scoped; moderator mutation actions and cross-path enforcement remain |
| Community Agent | IMPLEMENTED_UNVERIFIED | Logical safe-scope Agent answers rules and surfaces only public Posts |
| Candidate Pool and dynamic ranking | LIVE_VERIFIED | Multiple candidates, rank events, real A2A acceptance |
| Continuous offline monitoring | IMPLEMENTED_UNVERIFIED | Pub/Sub/reconciliation exists; required browser-closed scenario not accepted |
| Room lifecycle and summary | IMPLEMENTED_UNVERIFIED | Participant-scoped list/detail, V2 mapping, header facts and summary panel pass local tests/build |
| Three-channel isolation | IMPLEMENTED_UNVERIFIED | Server-isolated private, redacted read-only Agents-only, and consent-gated Shared channels exist |
| Dual-human approval | LIVE_VERIFIED | Version-bound atomic commit tests and live two-user acceptance |
| Match Detail and executable plan | IMPLEMENTED_UNVERIFIED | Participant-scoped direct list/detail routes and plan actions pass local tests/build; candidate acceptance remains |
| Calendar `.ics` export | IMPLEMENTED_UNVERIFIED | Authenticated participant-only escaped UTC calendar route and download UI pass local tests |
| Match change/cancel/backup | IMPLEMENTED_UNVERIFIED | Exact-version dual approval, audited cancellation, notifications, durable reopen event, and ranked backup activation pass local tests |
| Opt-in Contact Cards | LIVE_VERIFIED | Match-scoped offer/revoke and authorization implemented |
| Connections list/detail | IMPLEMENTED_UNVERIFIED | Owner-scoped list, eight views, direct detail, dimensions, plan/Room links, provenance, controls, and secondary Graph pass local tests/build |
| Connection reuse | IMPLEMENTED_UNVERIFIED | Personal Agent inspection/warm-introduction is task-context checked and usage-audited; candidate future-task acceptance remains |
| Memory lifecycle | IMPLEMENTED_UNVERIFIED | Typed grouped list/detail, confirmed-only scoped retrieval, usage events, Why-used provenance, task exceptions, contradiction review, and full controls pass local tests/build |
| Decision Inbox | PARTIAL | Decision records and badges exist; no unified route/filter/action product |
| In-app notifications | PARTIAL | Notifications exist; read state, category filters, mark-all-read and routing incomplete |
| Browser push | NOT_IMPLEMENTED | FCM web push intentionally waits for in-app notification acceptance |
| Action-specific Autonomy Center | PARTIAL | Typed per-action authority contract defaults to ask-first and forbids automatic final commitment; persistence, runtime enforcement, and UI remain |
| Admin authorization | LIVE_VERIFIED | Explicit admin claim enforced server-side |
| Admin operations console | PARTIAL | Dashboard exists; DLQ retry, model usage, moderation and lifecycle analytics incomplete |
| Account export/deletion | LIVE_VERIFIED | Authenticated routes and tests/evidence exist |
| Blocking/reporting | PARTIAL | Core routes exist; cross-surface and moderator acceptance incomplete |
| Product lifecycle analytics | NOT_IMPLEMENTED | Event log exists but no privacy-safe metric model/dashboard |
| Responsive/accessibility acceptance | NOT_IMPLEMENTED | No four-viewport visual and keyboard acceptance for V2 |
| Ten-user/three-Community V2 acceptance | NOT_IMPLEMENTED | Data volume exists; the required V2 scenario matrix has not run |
| Candidate deployment and production promotion | NOT_IMPLEMENTED | No Startup V2 candidate exists |
