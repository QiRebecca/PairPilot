# PairPilot V1 Live Acceptance Report

Date: 2026-09-01 (Asia/Shanghai)

## Deployed production

- User app/API: <https://pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app/>
- Orchestrator revision: `pairpilot-orchestrator-00028-nay` (100% traffic)
- Peer Agent revision: `pairpilot-peer-agents-00016-tel` (100% traffic)
- Runtime: `LIVE GEMINI + GOOGLE ADK + A2A`
- Exact model: `gemini-3.7-flash`
- Autoscaling: min 0, max 20, concurrency 16, request timeout 180 seconds
- Rollback: former production `pairpilot-orchestrator-00011-xeg` and verified candidate `00027-puw` remain ready.

## Five-user acceptance

The deterministic live gate `scripts/v1_live_acceptance.py` created and
authenticated five independent Firebase users and exercised the deployed
Firestore, Gemini/ADK, A2A, Pub/Sub and application APIs.

Result: `PASS`

| Assertion | Live evidence |
| --- | --- |
| Independent identities | 5 Firebase users |
| Offline discovery | Candidate count changed from 0 to 4 after the fifth user published |
| Dynamic ranking | 4 rank events |
| User isolation | Cross-user task read returned HTTP 403 |
| Dual approval | One atomic Match `proposal_3f769700c43578a545ba98d8` |
| Shared coordination | Room `room_567a8000a2d241ca48b53c44` unlocked after both approvals |
| Contact privacy | Match-scoped contact card exchange verified |
| Memory authority | Proposed memory excluded; confirmed memory retrieved |
| Outcome learning | Outcome record and private feedback verified |
| Safety | Block, report, export/delete propagation verified |

The run suffix was `20260831183955`. Private canary instructions were not
present in public or peer-Agent projections.

## Reliability and deployment gates

- Python suite: 82 passed.
- Frontend: lint passed, 5 tests passed, production build passed.
- Infrastructure smoke: 50/50 concurrent health requests returned HTTP 200.
- Pub/Sub: permanent OIDC push subscription points to production, 120-second ack deadline, 10–60 second retry, five-attempt DLQ.
- Reconciliation: Cloud Scheduler calls production every five minutes through OIDC; an immediate post-cutover run succeeded.
- Dead-letter inspection: empty after cutover.
- Browser: public landing, sign-in, restored authenticated Agent workspace, persistent chat composer, full navigation and completed request history were inspected in the deployed app.

## Explicitly remaining outside this release

- FCM browser push is not implemented; in-app notifications are the reliable shipped channel.
- Password-reset mail delivery, long-duration SSE network soak, and deliberate material-change race injection remain unverified live gates.
- Non-room-share intent types share generic policy; invite/moderator management, warm-introduction acceptance, and a dedicated working-belief UI remain partial.

These items are intentionally recorded as gaps rather than represented as
finished behavior.
