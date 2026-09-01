# Startup V2 product completion matrix

Updated: 2026-09-01

Only `NOT_IMPLEMENTED`, `PARTIAL`, `IMPLEMENTED_UNVERIFIED`, and `LIVE_VERIFIED`
are valid completion states.

| Capability | Status | Current evidence / missing gate |
|---|---|---|
| Submission snapshot and rollback | LIVE_VERIFIED | Git tag, submitted revision, digest, rollback command recorded |
| Persistent Personal Agent multi-turn chat | LIVE_VERIFIED | Production real-Gemini two-turn and multi-user acceptance |
| Authenticated multi-user isolation | LIVE_VERIFIED | Firebase principals, owner checks, deny-all Firestore browser rules, tests |
| Unified V2 schema and state machines | PARTIAL | V1 entities exist; lifecycle vocabularies and version history are inconsistent |
| Versioned migration framework | NOT_IMPLEMENTED | No schema registry, dry-run runner, export gate, or migration report |
| Request workspace tabs and activity | PARTIAL | Request route works; required tabbed workspace and material-change invalidation missing |
| Explore natural-language and structured search | PARTIAL | Keyword/tag client filter and public feed exist; no server hybrid retrieval or filters |
| Saved Posts and saved searches | NOT_IMPLEMENTED | No authoritative entities or routes |
| Post Detail route | NOT_IMPLEMENTED | Explore uses a modal, not `/app/posts/:intentId` |
| Agent evaluate/contact from Post | PARTIAL | Contact API exists; no complete evaluate/create-related-request flow |
| Community join/leave | LIVE_VERIFIED | Authenticated APIs and production data exist |
| Community Detail and scoped feed | NOT_IMPLEMENTED | No direct Community route or tabs |
| Community rules and moderation | PARTIAL | Reports/blocking exist; rule enforcement and moderator actions incomplete |
| Community Agent | NOT_IMPLEMENTED | No scoped logical Community Agent |
| Candidate Pool and dynamic ranking | LIVE_VERIFIED | Multiple candidates, rank events, real A2A acceptance |
| Continuous offline monitoring | IMPLEMENTED_UNVERIFIED | Pub/Sub/reconciliation exists; required browser-closed scenario not accepted |
| Room lifecycle and summary | PARTIAL | Real Rooms/messages exist; V2 state machine and summary panel missing |
| Three-channel isolation | PARTIAL | Private Agent and Agents-only controls exist; complete shared-channel UX/audit missing |
| Dual-human approval | LIVE_VERIFIED | Version-bound atomic commit tests and live two-user acceptance |
| Match Detail and executable plan | PARTIAL | Match list/shared Room/contact/outcome exist; detail route and plan operations missing |
| Calendar `.ics` export | NOT_IMPLEMENTED | No route or artifact generation |
| Match change/cancel/backup | NOT_IMPLEMENTED | No complete versioned lifecycle |
| Opt-in Contact Cards | LIVE_VERIFIED | Match-scoped offer/revoke and authorization implemented |
| Connections list/detail | PARTIAL | Relationships and graph/list content exist under Network; no V2 routes or actions |
| Connection reuse | IMPLEMENTED_UNVERIFIED | Warm-introduction tool exists; future-task behavioral acceptance missing |
| Memory lifecycle | PARTIAL | propose/confirm/reject/archive/delete exist; types, usage events and scope evidence incomplete |
| Decision Inbox | PARTIAL | Decision records and badges exist; no unified route/filter/action product |
| In-app notifications | PARTIAL | Notifications exist; read state, category filters, mark-all-read and routing incomplete |
| Browser push | NOT_IMPLEMENTED | FCM web push intentionally waits for in-app notification acceptance |
| Action-specific Autonomy Center | NOT_IMPLEMENTED | Current coarse mode cannot express per-action policies |
| Admin authorization | LIVE_VERIFIED | Explicit admin claim enforced server-side |
| Admin operations console | PARTIAL | Dashboard exists; DLQ retry, model usage, moderation and lifecycle analytics incomplete |
| Account export/deletion | LIVE_VERIFIED | Authenticated routes and tests/evidence exist |
| Blocking/reporting | PARTIAL | Core routes exist; cross-surface and moderator acceptance incomplete |
| Product lifecycle analytics | NOT_IMPLEMENTED | Event log exists but no privacy-safe metric model/dashboard |
| Responsive/accessibility acceptance | NOT_IMPLEMENTED | No four-viewport visual and keyboard acceptance for V2 |
| Ten-user/three-Community V2 acceptance | NOT_IMPLEMENTED | Data volume exists; the required V2 scenario matrix has not run |
| Candidate deployment and production promotion | NOT_IMPLEMENTED | No Startup V2 candidate exists |

