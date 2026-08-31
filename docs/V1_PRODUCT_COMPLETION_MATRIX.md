# PairPilot V1 Product Completion Matrix

Audit date: 2026-09-01 (Asia/Shanghai)

Allowed status values are exactly `NOT_IMPLEMENTED`, `PARTIAL`,
`IMPLEMENTED_UNVERIFIED`, and `LIVE_VERIFIED`. `LIVE_VERIFIED` means the
capability ran against the deployed Google Cloud/Firebase stack, not merely in
an in-memory unit test.

| Capability | Status | Evidence / missing gate |
| --- | --- | --- |
| Email/password sign-up and sign-in | LIVE_VERIFIED | Five independent Firebase users authenticated in the live V1 gate. |
| Email verification and guarded social actions | LIVE_VERIFIED | All five controlled accounts were independently verified before publish/match actions. |
| Sign-out and session restore | LIVE_VERIFIED | Authenticated browser session restored on the deployed app. |
| Password reset | IMPLEMENTED_UNVERIFIED | Firebase email-link UI exists; external mail delivery was not exercised in this gate. |
| Account disable | PARTIAL | Disabled status is enforced; an admin mutation UI is not shipped. |
| Account export and deletion | LIVE_VERIFIED | Five-user script exercised account export/deletion and cross-user isolation. |
| Persistent user-owned Personal Agent | LIVE_VERIFIED | Distinct users received distinct Agent IDs and persistent global/task sessions. |
| Real Gemini/ADK runtime | LIVE_VERIFIED | Production health reports `LIVE GEMINI + GOOGLE ADK + A2A`, model `gemini-3.7-flash`. |
| Authenticated SSE and reconnect | IMPLEMENTED_UNVERIFIED | Replay/unit coverage exists; extended network-disruption soak was not run. |
| Honest model failure and provenance | LIVE_VERIFIED | No canned assistant fallback; model/session/invocation/tool/token metadata is persisted. |
| Conversation-first `/app/agent` | LIVE_VERIFIED | Authenticated browser gate shows the persistent chat composer and request history. |
| Independent Task Workspaces | LIVE_VERIFIED | Five live users created isolated tasks; cross-user task read returned HTTP 403. |
| Typed V1 intent types | PARTIAL | Five canonical types are accepted; ROOM_SHARE has the deepest policy, the other four use shared generic policy. |
| Agent-generated Post draft | LIVE_VERIFIED | Gemini-generated draft, private boundary, human confirmation, and publication ran live. |
| Three-layer Post review | LIVE_VERIFIED | UI/API exposes public post, private Agent context, and publish controls separately. |
| Cancel, revise, continue discussion | LIVE_VERIFIED | Draft review actions and continued Personal Agent conversation are implemented. |
| Pause, resume, close and expiry | LIVE_VERIFIED | Lifecycle routes, events, and reconciliation handling are deployed and tested. |
| Public/private projections | LIVE_VERIFIED | Private instructions and contact data are excluded from public/A2A projections. |
| Public Communities and membership | LIVE_VERIFIED | ICML Seoul community, join/leave, membership guard and leave-triggered post pause are live. |
| Invites and moderator operations | PARTIAL | Invite-required and role fields are enforced in the domain; moderator management UI is absent. |
| Community-scoped Explore | LIVE_VERIFIED | Feed and matching require a shared active community. |
| Candidate Pool and candidate Rooms | LIVE_VERIFIED | Five-user gate produced four candidates and an independent room per candidate pair. |
| Inspect up to 20 and contact up to 5 | LIVE_VERIFIED | Deployed coordinator enforces 20 inspected / 5 contacted caps. |
| Three simultaneous negotiations | LIVE_VERIFIED | Coordinator uses bounded batches of three and persists independent candidate states. |
| Six-round bounded A2A | PARTIAL | Hard six-round ceiling exists; current automatic evaluation normally resolves in one substantive round. |
| Real peer-Agent Gemini turns | LIVE_VERIFIED | Independently owned Agents generated live assessments; no synthetic candidate fallback. |
| Evidence separation and conflicts | LIVE_VERIFIED | Verified, peer-reported, negotiated, conflict, and uncertainty fields are stored per assessment. |
| Dynamic ranking and rank audit | LIVE_VERIFIED | Four rank-change events were observed in the live gate. |
| Primary, backups, stop and availability changes | LIVE_VERIFIED | Ranked list, prepare-proposal, backup, withdraw and rerank paths are implemented and tested. |
| Private task instruction | LIVE_VERIFIED | Unique private instruction canary was absent from public/A2A output. |
| Event-driven publication worker | LIVE_VERIFIED | Permanent Pub/Sub subscription targets the production service with OIDC. |
| Offline new-Post reevaluation | LIVE_VERIFIED | User 1 had zero candidates, user 5 later published, then user 1 gained four candidates without reopening the UI. |
| Periodic reconciliation | LIVE_VERIFIED | Cloud Scheduler invokes production `/api/internal/reconcile` every five minutes using OIDC. |
| Dead-letter and recovery | LIVE_VERIFIED | Five-attempt DLQ policy and inspection subscription are active; post-deploy queue was empty. |
| Unified in-app notifications | LIVE_VERIFIED | Notification collection, preference suppression, page and lifecycle producers are deployed. |
| FCM web push | NOT_IMPLEMENTED | Browser push token/service-worker/permission flow remains intentionally outside this release. |
| Versioned Proposal, Hold and two Agent acceptances | LIVE_VERIFIED | Proposal, hold and independent Agent acceptance records were persisted. |
| Two independent human approvals and atomic Match | LIVE_VERIFIED | First approval waited; second atomically created one Match and one shared Room. |
| Material-change approval invalidation | IMPLEMENTED_UNVERIFIED | Code/unit tests exist; a dedicated live mutation race was not injected. |
| Shared Human-Agent Room | LIVE_VERIFIED | Human messaging unlocked only after both people approved. |
| Match-scoped Contact Card | LIVE_VERIFIED | Explicit offer/exchange/revoke scope ran in the live gate; default remains no contact sharing. |
| Confirmed-only global Memory | LIVE_VERIFIED | Proposed memory was excluded until user confirmation; confirmed memory was retrieved. |
| Task, episodic and relational Memory | LIVE_VERIFIED | Task context, outcome memory and relationship evidence are persisted with provenance. |
| Working-belief separation | PARTIAL | Belief records remain non-authoritative, but no dedicated belief-management UI is shipped. |
| Memory confirm/edit/reject/archive/delete | LIVE_VERIFIED | Authenticated lifecycle API/UI and owner isolation are implemented. |
| Relationship provenance and Network | LIVE_VERIFIED | Network page exposes relationship events, counters and provenance. |
| Warm introductions | PARTIAL | Reuse tools exist; no separate live warm-introduction acceptance scenario was run. |
| Outcome check-in | LIVE_VERIFIED | Private feedback, authoritative relationship event and proposed memory ran live. |
| Block, report and leave Room | LIVE_VERIFIED | Live gate exercised block/report; propagation closes rooms/proposals and releases holds. |
| Terms and privacy pages | LIVE_VERIFIED | Public deployed routes render current product policies. |
| Explicit admin claims and console | LIVE_VERIFIED | `/api/admin/dashboard` rejects ordinary users and returns only aggregates to explicit admins. |
| Configurable quotas and layered rate limits | PARTIAL | Core caps are configurable; rate limiting remains primarily endpoint/IP based. |
| Prompt-injection and privacy policy | LIVE_VERIFIED | Public/A2A guard rejects email, phone, room/address, coordinates and sensitive current-state phrases. |
| Product analytics | PARTIAL | Aggregate operational metrics exist; a full funnel/retention taxonomy is not shipped. |
| User-scoped Audit | LIVE_VERIFIED | Authenticated audit endpoint and HTTP 403 IDOR gate passed. |
| Presentation directives | PARTIAL | Allowlist is persisted; authenticated renderer supports only the current card set. |
| Premium responsive authenticated UI | LIVE_VERIFIED | Landing/sign-in/authenticated desktop workspace were browser-verified; responsive CSS/build gates pass. |
| Role-separated Room UI | LIVE_VERIFIED | Human/Agent authorship and locked/unlocked modes are visibly separated. |
| Five-user live acceptance | LIVE_VERIFIED | `scripts/v1_live_acceptance.py` passed all required invariants with five Firebase users. |
| 20–50 request infrastructure smoke | LIVE_VERIFIED | 50 concurrent health requests returned 50 HTTP 200 responses after candidate deploy. |
| Dependency and secret audit | LIVE_VERIFIED | Current npm/pip/diff scans pass; no secret was added to source control. |
| Production current-worker deployment | LIVE_VERIFIED | Orchestrator revision `00028-nay` and peer revision `00016-tel` serve 100%; worker and Scheduler target production. |
| Rollback revision | LIVE_VERIFIED | Prior production revision `00011-xeg`, candidate `00027-puw`, and tag `pre-v1-complete-20260901` remain available. |
