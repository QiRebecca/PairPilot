# PairPilot V1 Product Completion Matrix

Audit date: 2026-09-01 (Asia/Shanghai)

Allowed status values are exactly `NOT_IMPLEMENTED`, `PARTIAL`,
`IMPLEMENTED_UNVERIFIED`, and `LIVE_VERIFIED`.

| Capability | Status | Evidence / missing gate |
| --- | --- | --- |
| Email/password sign-up | LIVE_VERIFIED | Firebase controlled users authenticated live. |
| Email verification | LIVE_VERIFIED | Verified test accounts and guarded app routes. |
| Sign-in, sign-out, session restore | LIVE_VERIFIED | Auth provider and live E2E. |
| Password reset | IMPLEMENTED_UNVERIFIED | UI/API exists; no recorded live email-link gate. |
| Account disable | PARTIAL | Account status is checked; admin disable workflow absent. |
| Account deletion | IMPLEMENTED_UNVERIFIED | Source/tests exist; V1 live gate missing. |
| One persistent Personal Agent per user | LIVE_VERIFIED | Two distinct users/Agent IDs exercised live. |
| Generic user-owned Agent runtime | LIVE_VERIFIED | No fixed identity in authenticated runtime. |
| Persistent global ADK session | LIVE_VERIFIED | Follow-up and restore proven live. |
| Persistent task ADK session | LIVE_VERIFIED | Draft/publish task turns proven live. |
| Persistent intent-pair A2A session | LIVE_VERIFIED | Two-sided live A2A sessions persisted. |
| Authenticated SSE and reconnect | IMPLEMENTED_UNVERIFIED | Unit replay coverage; full V1 reliability gate pending. |
| Honest model failure | LIVE_VERIFIED | No canned assistant saved; frontend test passes. |
| Agent response provenance | LIVE_VERIFIED | Model/session/invocation/tool/token metadata persisted. |
| Conversation-first `/app/agent` | LIVE_VERIFIED | Candidate UI and live chat verified. |
| Independent Task Workspaces | LIVE_VERIFIED | Real user tasks and task conversations persisted. |
| Typed ROOM_SHARE policy | PARTIAL | Matching fields exist; schema/policy needs V1 freeze. |
| Other V1 intent-type policies | NOT_IMPLEMENTED | Shared infrastructure only; typed policies absent. |
| Agent-generated Post draft | LIVE_VERIFIED | Gemini selected draft tool in live run. |
| Three-layer Post review | PARTIAL | Public/private split exists; UI does not present all three layers. |
| Edit/approve/publish Post | LIVE_VERIFIED | Structured review and exact chat authority both work. |
| Cancel/ask-revise/continue-discussing controls | PARTIAL | Conversation works; full action card controls absent. |
| Pause/resume/close Post | IMPLEMENTED_UNVERIFIED | Source exists; complete live lifecycle pending. |
| Post expiry | NOT_IMPLEMENTED | No expiry worker/reconciliation. |
| Public/private Post projections | LIVE_VERIFIED | Owner-private goal/email excluded from public projection. |
| Public event Communities | NOT_IMPLEMENTED | No Community domain/API/UI. |
| Community membership/invites | NOT_IMPLEMENTED | No membership policy or invite flow. |
| Community moderators | NOT_IMPLEMENTED | No role/operations flow. |
| Community-scoped Explore | NOT_IMPLEMENTED | Explore is global OPEN feed. |
| Post-centric Explore | PARTIAL | Public feed exists; tabs/filters/reasons/actions incomplete. |
| Candidate Pool | PARTIAL | Assessment collection/tools exist; automatic pool lifecycle absent. |
| Inspect up to 20 Posts | NOT_IMPLEMENTED | Current worker selects from unranked OPEN list. |
| Contact up to 5 candidates | NOT_IMPLEMENTED | Automatic flow stops at first candidate. |
| Three simultaneous negotiations | NOT_IMPLEMENTED | Quota field exists; coordinator absent. |
| Six-round bounded A2A | NOT_IMPLEMENTED | Current A2A is a bounded single pair turn. |
| Real peer-Agent Gemini turns | LIVE_VERIFIED | Two independently owned Agents ran live. |
| Candidate evidence separation | PARTIAL | Some status fields exist; frozen evidence schema absent. |
| Dynamic ranking | NOT_IMPLEMENTED | No material-change reranker. |
| Rank-change audit events | NOT_IMPLEMENTED | No previous/new ordering event. |
| Primary and backup candidates | NOT_IMPLEMENTED | Current first proposal blocks further search. |
| Candidate Rooms | PARTIAL | Proposal Room exists; not every candidate receives one. |
| Private task instruction | LIVE_VERIFIED | Live test proved reason stayed out of A2A text. |
| Event-driven Post publication | LIVE_VERIFIED | Pub/Sub publication worked under temporary current worker. |
| Current permanent worker topology | PARTIAL | Subscription targets old multi-user-beta tag. |
| Full Post lifecycle events | NOT_IMPLEMENTED | Updated/expired/matched event reactions incomplete. |
| Offline new-Post reevaluation | PARTIAL | Event mechanics exist; V1 test and pool update absent. |
| Periodic reconciliation | NOT_IMPLEMENTED | No Scheduler job. |
| Dead-letter and recovery | NOT_IMPLEMENTED | Push subscription has no DLQ. |
| Unified in-app notifications | NOT_IMPLEMENTED | No notification collection/page. |
| FCM web push | NOT_IMPLEMENTED | Deferred until in-app notifications. |
| Versioned Proposal | LIVE_VERIFIED | Version 1 proposal persisted and audited. |
| Active Hold | LIVE_VERIFIED | Hold enforced in two-user gate. |
| Two Agent acceptances | LIVE_VERIFIED | Acceptance records persisted. |
| Two independent human approvals | LIVE_VERIFIED | First waited; second committed. |
| Atomic Match | LIVE_VERIFIED | One Match and shared Room created exactly once. |
| Material-change approval invalidation | IMPLEMENTED_UNVERIFIED | Source path exists; V1 live gate pending. |
| Shared Human-Agent Room | LIVE_VERIFIED | Dual-approved Room unlocked in live gate. |
| Match-scoped Contact Card | NOT_IMPLEMENTED | No opt-in contact offer/exchange entities. |
| Confirmed global Memory | PARTIAL | Memory exists but status filter is unsafe. |
| Task memory | PARTIAL | Private task instructions exist; lifecycle/schema incomplete. |
| Episodic Memory | PARTIAL | Match outcome memory exists; lifecycle UI incomplete. |
| Relational Memory | PARTIAL | Relationship records exist; context/provenance thin. |
| Working belief separation | NOT_IMPLEMENTED | Existing beliefs are not integrated into V1 lifecycle. |
| Memory confirm/edit/reject/archive/delete | PARTIAL | Older demo endpoints/UI exist; authenticated V1 missing. |
| Confirmed-only retrieval | NOT_IMPLEMENTED | Proposed/reviewable records can enter current context. |
| Relationship provenance/network | PARTIAL | Basic relationships exist; authenticated evidence UI absent. |
| Warm introductions | PARTIAL | Tool exists; generic V1 live reuse absent. |
| Outcome check-in | NOT_IMPLEMENTED | No scheduled lifecycle or user page. |
| Block user | IMPLEMENTED_UNVERIFIED | Discovery checks exist; full V1 propagation gate pending. |
| Report user/Post | IMPLEMENTED_UNVERIFIED | API and UI controls exist; moderation queue absent. |
| Leave Room | IMPLEMENTED_UNVERIFIED | Source exists; live safety gate pending. |
| Account export | IMPLEMENTED_UNVERIFIED | Source/UI exists; live gate pending. |
| Terms and privacy pages | IMPLEMENTED_UNVERIFIED | Pages exist; content/visual/live review pending. |
| Explicit admin claims | PARTIAL | Claim parser/guard exists; no admin product. |
| Admin console | NOT_IMPLEMENTED | No authenticated `/admin` capabilities. |
| Configurable usage quotas | PARTIAL | Several hardcoded/default quotas persist. |
| UID/IP/endpoint/task/recipient rate limits | PARTIAL | Basic middleware only. |
| Prompt-injection/privacy policy | PARTIAL | Agent instructions and filters exist; full adversarial suite absent. |
| Product analytics events | NOT_IMPLEMENTED | Required event taxonomy/dashboard absent. |
| User-scoped Audit | LIVE_VERIFIED | Authenticated audit endpoint and IDOR gate. |
| Presentation directives | PARTIAL | Persisted allowlist; authenticated renderer incomplete. |
| Premium responsive authenticated UI | PARTIAL | Core pages work; required routes/states/mobile QA incomplete. |
| Role-separated Room UI | PARTIAL | Authorship shown; full channel/mode model incomplete. |
| Five-user live acceptance | NOT_IMPLEMENTED | Only two controlled live users exercised together. |
| 20–50 user infrastructure smoke | NOT_IMPLEMENTED | No recorded test. |
| Dependency and secret audit | LIVE_VERIFIED | Current npm/pip/diff scans passed before V1 changes. |
| Production current-worker deployment | NOT_IMPLEMENTED | Production and worker remain older revisions. |
| Rollback revision | LIVE_VERIFIED | Older ready revisions and 100% current production remain. |

