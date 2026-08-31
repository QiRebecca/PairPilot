# PairPilot V1 Live Acceptance Report

Date: 2026-09-01 (Asia/Shanghai)

## Deployed production

- User app/API: <https://pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app/>
- Orchestrator revision: `pairpilot-orchestrator-00035-beq` (100% traffic)
- Peer Agent revision: `pairpilot-peer-agents-00022-seh` (100% traffic)
- Runtime: `LIVE GEMINI + GOOGLE ADK + A2A`
- Exact model: `gemini-3.7-flash`
- Orchestrator autoscaling: min 0, max 20, concurrency 16, timeout 180 seconds
- Peer Agent autoscaling: min 0, max 20, concurrency 4, timeout 90 seconds
- Pub/Sub push and the five-minute reconciliation scheduler use authenticated
  production URLs.

## Multi-user and multi-Agent acceptance

The live gate `scripts/v1_multi_intent_live_acceptance.py` was run three times
against no-traffic candidate revisions. Each run created 16 independent
Firebase identities: ten users forming five real matches, five users keeping
open seed Posts for continued discovery, and one disposable account for
export/deletion validation.

All three runs returned `PASS`:

- `multi-20260901-0357`
- `multi-final-20260901-0420`
- `multi-true-peer-20260901-0435`

Aggregate evidence:

| Assertion | Live evidence |
| --- | --- |
| Independent identities | 48 test identities across three runs |
| Persistent Personal Agent chat | 30 live Gemini/ADK turns completed, 0 failed |
| Intent coverage | ROOM_SHARE, MEAL_COMPANION, COFFEE_CHAT, EVENT_BUDDY, HACKATHON_TEAMMATE |
| Private-to-public workflow | Agent-created private task, reviewed draft, explicit publish |
| Offline discovery | Pub/Sub worker plus five-minute reconciliation safety net |
| Agent negotiation | Two fresh Personal Agent messages recorded per candidate room |
| Dynamic ranking | Candidate assessment and rank events persisted for every scenario |
| Completed matches | 15 dual-approved matches and 15 unlocked shared rooms |
| Persistent open supply | 15 open seed Posts remain available across all five intent types |
| User isolation | Every cross-user task read returned HTTP 403 |
| Contact privacy | Match-scoped contact exchange appeared only after both approvals |
| Memory authority | Proposed memory excluded; confirmed memory retrieved |
| Outcome learning | Match outcome and private feedback persisted |
| Safety | Sensitive public Post rejected; report and block verified |
| Account lifecycle | Export returned data; disposable account deletion propagated |

Private canary instructions were absent from public Posts and peer-Agent
messages in every run.

## Production cutover smoke

- The original failure shape was reproduced after cutover: one clarification
  message followed by a second task-creation message. Both Agent invocations
  completed and created a `HACKATHON_TEAMMATE` task in `DRAFT` state.
- The four recorded acceptance suffixes contain 32 live Personal Agent
  invocations in total: 32 `COMPLETED`, 0 `FAILED`, all on
  `gemini-3.7-flash`.
- 60/60 concurrent production health requests returned HTTP 200.
- An unauthenticated private bootstrap request returned the expected HTTP 401.
- Production Pub/Sub event consumption returned HTTP 200.
- Two production reconciliation calls returned HTTP 200.
- No production `job_failures` were created after cutover.
- The dead-letter inspection subscription was empty after old pre-fix test
  messages were verified as already reconciled and acknowledged.

## Direct A2A acceptance

Alice, Maya, and Lena were called through their official A2A 1.0 Agent Cards
on both candidate and production Peer revisions. The production cards advertise
the canonical production service URL. All three JSON-RPC calls returned HTTP
200 with validated, non-empty envelopes.

When Vertex AI or the model does not return a valid structured answer after
bounded retries, the Peer Agent now returns an explicit zero-confidence
nonresponse with no claims or human commitment. It does not fabricate an answer
or fail the A2A request.

## Reliability gates

- Python: Ruff passed; 98 tests passed.
- Frontend: ESLint passed; 5 tests passed; production build passed.
- Candidate concurrency: 60/60 health requests returned HTTP 200.
- Production concurrency: 60/60 health requests returned HTTP 200.
- Final Orchestrator log audit: 70 HTTP 200 responses, one expected HTTP 401,
  zero HTTP 5xx, zero ERROR/CRITICAL entries.
- Final Peer log audit: three A2A calls and three Agent Card reads returned HTTP
  200, zero HTTP 5xx, zero ERROR/CRITICAL entries.
- Final production traffic is pinned to the exact Orchestrator and Peer
  revisions listed above; older revisions remain available for rollback.

## Defects found and closed during acceptance

- A stale `peer_coordination` tool value broke the second Personal Agent turn;
  canonical five-type resolution now occurs at the tool boundary.
- Public dates containing hyphens were incorrectly treated as phone numbers;
  privacy patterns now distinguish dates/test identifiers from contact data.
- Reconciliation repeatedly selected the same first Posts; it now rotates
  fairly by `last_reconciled_at`.
- A Firestore query requested an invalid limit of 200; the bounded query now
  uses the supported maximum of 100 and has a regression test.
- Candidate OIDC audiences initially pointed at a different Cloud Run host;
  Pub/Sub and Scheduler now use matching endpoint/audience pairs.
- Peer Agent Cards advertised an old tagged revision; final cards now advertise
  the canonical production service URL.
- Empty, invalid, rate-limited, or transiently failed model output could surface
  as an A2A failure; it now retries within the service deadline and fails safe
  with explicit provenance.

## Scope note

No finite test program can prove that software has zero possible defects. This
report establishes that there are no known open failures in the exercised V1
matrix. FCM browser push is still not part of this release; reliable in-app
notifications, authenticated Pub/Sub processing, and periodic reconciliation
are the shipped update channels.
