# Startup V2 product completion matrix

Updated: 2026-09-08

Only `NOT_IMPLEMENTED`, `PARTIAL`, `IMPLEMENTED_UNVERIFIED`, and `LIVE_VERIFIED`
are valid completion states.

| Capability | Status | Current evidence / missing gate |
|---|---|---|
| Submission snapshot and rollback | LIVE_VERIFIED | Git tag, submitted revision, digest, rollback command recorded |
| Persistent Personal Agent multi-turn chat | LIVE_VERIFIED | Candidate global conversation completed live draft, revise and explicit publish after the post-tool 429 failure was reproduced and fixed |
| Authenticated multi-user isolation | LIVE_VERIFIED | Firebase principals, owner checks, deny-all Firestore browser rules, tests |
| Unified V2 schema and state machines | PARTIAL | Canonical Post, Room, Match, Connection, Memory, Decision, Notification, and action-autonomy vocabularies plus validators exist; legacy Room/Match/Connection runtime writes still need migration |
| Versioned migration framework | IMPLEMENTED_UNVERIFIED | Registry, checksums, pagination, dry-run, optimistic concurrency, environment/backup guards, migration report, and real 3,093-record dry-run pass; candidate apply is still gated |
| Request workspace tabs and activity | IMPLEMENTED_UNVERIFIED | Conversation-default seven-tab route, Overview, Post, Candidates, Agent Rooms, Activity, Audit and explicit Request closure pass component/build checks; live closure released quota and withdrew stale state, but authenticated browser acceptance remains |
| Explore natural-language and structured search | PARTIAL | Authenticated server filters, six views, bounded text relevance, result explanations, and local browser acceptance pass; Firestore vector index and embedding backfill remain gated |
| Saved Posts and saved searches | LIVE_VERIFIED | Save/remove/reactivate semantics, active monitor creation, existing/new Post Pub/Sub evaluation, scope/block checks, idempotent hits and clickable in-app notification passed live candidate acceptance |
| Post Detail route | LIVE_VERIFIED | Authorized `/app/posts/:intentId` public-only API and saved-search notification direct link passed candidate acceptance without private-field leakage |
| Agent evaluate/contact from Post | LIVE_VERIFIED | Eight candidate contacts produced real Gemini/ADK/A2A turns, evidence-backed assessments and Rooms across independent users |
| Community join/leave | LIVE_VERIFIED | Authenticated APIs and production data exist |
| Community Detail and scoped feed | IMPLEMENTED_UNVERIFIED | Direct route, five tabs, scoped Posts/members/Rooms pass local tests and browser acceptance |
| Community rules and moderation | PARTIAL | Scoped moderator queue/actions, removal/suspension authority, untrusted-content warning, and audit exist locally; cross-path and candidate acceptance remain |
| Community Agent | IMPLEMENTED_UNVERIFIED | Logical safe-scope Agent answers rules and surfaces only public Posts |
| Candidate Pool and dynamic ranking | LIVE_VERIFIED | Multiple candidates, rank events, real A2A acceptance |
| Continuous offline monitoring | LIVE_VERIFIED | OIDC Pub/Sub push evaluated saved searches and created authorized notifications without browser participation; reconciliation and candidate availability also run through the isolated worker |
| Room lifecycle and summary | IMPLEMENTED_UNVERIFIED | Participant-scoped list/detail, V2 mapping, header facts and summary panel pass local tests/build |
| Three-channel isolation | IMPLEMENTED_UNVERIFIED | Private Room view now uses the same live task-scoped Personal Agent; redacted read-only Agents-only and consent-gated Shared channels remain server-isolated; shared Agent draft approval remains |
| Dual-human approval | LIVE_VERIFIED | Version-bound atomic commit tests and live two-user acceptance |
| Match Detail and executable plan | LIVE_VERIFIED | Participant-scoped list/detail, outsider denial, Room link and plan actions passed the live lifecycle matrix |
| Calendar `.ics` export | LIVE_VERIFIED | Authenticated participant-only calendar output passed live validation |
| Match change/cancel/backup | LIVE_VERIFIED | Exact-version dual approval, cancellation and same-Request-only ranked backup activation passed live candidate matrices |
| Opt-in Contact Cards | LIVE_VERIFIED | Match-scoped offer/revoke and authorization implemented |
| Connections list/detail | IMPLEMENTED_UNVERIFIED | Owner-scoped list, eight views, direct detail, dimensions, plan/Room links, provenance, controls, and secondary Graph pass local tests/build |
| Connection reuse | LIVE_VERIFIED | Nine-turn candidate context matrix proved applicable reuse, mismatched-context refusal and usage audit |
| Memory lifecycle | LIVE_VERIFIED | Candidate context matrix proved proposed Memory inert, confirmed in-scope use, out-of-scope exclusion, why-used evidence, task override and rejection stop |
| Decision Inbox | PARTIAL | Owner-scoped unified route, badges, exact entity routing, reject, and safe inline approval for supported types pass locally; remaining types need inline handlers |
| In-app notifications | LIVE_VERIFIED | Live saved-search notification, public Post routing and authorization passed; read/archive/preferences remain covered locally |
| Browser push | NOT_IMPLEMENTED | FCM web push intentionally waits for in-app notification acceptance |
| Action-specific Autonomy Center | PARTIAL | Twelve-action global/task UI, persistence, locked final commitment, history, and Post-publish enforcement exist; remaining Agent actions need common enforcement |
| Admin authorization | LIVE_VERIFIED | Explicit admin claim enforced server-side |
| Admin operations console | IMPLEMENTED_UNVERIFIED | Fourteen-section role-protected console, report detail/actions, idempotent failed-job/DLQ actions, quotas, model usage, deletion queue and audit pass local tests/build; candidate/provider acceptance remains |
| Account export/deletion | LIVE_VERIFIED | Authenticated routes and tests/evidence exist |
| Blocking/reporting | PARTIAL | Core routes exist; cross-surface and moderator acceptance incomplete |
| Product lifecycle analytics | IMPLEMENTED_UNVERIFIED | Content-free lifecycle counts and derived plan/approval/completion/cancellation/Connection/Memory metrics are operational locally; canonical event coverage and candidate acceptance remain |
| Responsive/accessibility acceptance | PARTIAL | New route semantics, focus, reduced-motion, offline announcement, tablet/mobile layouts, route-split 282 kB main bundle and 15 frontend tests pass; authenticated four-viewport visual/keyboard/screen-reader acceptance remains |
| Ten-user/three-Community V2 acceptance | LIVE_VERIFIED | Candidate runs exercised 10 auth users, 3 Communities, 25 Posts, 5 types, 8 Agent contacts, 7 Matches, 4 completions, 3 cancellations, 20 Memories and 80 concurrent authenticated requests |
| Candidate deployment and production promotion | PARTIAL | Isolated revision `00062-zor`, immutable digest, prefix, topic, OIDC subscription and DLQ are live at zero traffic; migration apply, visual/failure-injection gates and production promotion remain |
