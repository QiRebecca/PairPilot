# PairPilot Final Evidence Index

Evidence cut: 2026-09-01 (Asia/Shanghai)

This index separates evidence already recorded by a reproducible live gate from
video shots that have not yet been recorded. A timestamp marked **planned** is a
runbook target, not a claim that footage exists.

## Final candidate runtime

| Item | Final candidate value |
| --- | --- |
| Production URL | <https://pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app/> |
| Google Cloud project | `pairpilot-agentic-ecb84a` |
| Region / Firestore location | `europe-west2` / `europe-west2` |
| Production orchestrator | `pairpilot-orchestrator-00045-tig` (100% traffic; tag `submission-prod`) |
| Final orchestrator image | `sha256:4aded86e939fe18e8beffa9d9a1a2ee731436cb8509c6d5631252e7123e2fb1a` |
| Rollback orchestrator | `pairpilot-orchestrator-00039-joh` |
| Peer Agent revision | `pairpilot-peer-agents-00022-seh` (100% traffic) |
| Peer Agent image | `sha256:bfe8e9477136f848db5e3eb6af14d6fe1982f56f0a5723a5c7964120f5f12b70` |
| Agent model | `gemini-3.7-flash` on Vertex AI |
| Runtime mode | `LIVE GEMINI + GOOGLE ADK + A2A` |

The final judge requester cohort on production has three ranked candidates, five
private Agent/negotiation rooms, one Shared Room, one committed match, one
relationship and one confirmed memory. A separate late-candidate account holds
an unpublished compatible Task for the continuous-discovery demonstration. Two
consecutive task-focused turns completed in the same persistent global chat.
The production health concurrency check returned 60/60 HTTP 200. These are
controlled test records, not organic marketplace activity.

## Claim-to-proof matrix

| Claim | Source file | Reproducible test / inspection | Production run or record reference | Cloud Run revision | Authoritative Firestore record type | Video timestamp |
| --- | --- | --- | --- | --- | --- | --- |
| A registered user has one real persistent Personal Agent conversation | [`REAL_AGENT_RESPONSE_PROVENANCE.md`](REAL_AGENT_RESPONSE_PROVENANCE.md), [`V1_LIVE_ACCEPTANCE_REPORT.md`](V1_LIVE_ACCEPTANCE_REPORT.md) | `scripts/verify_qi_persistent_chat.py`; two consecutive turns returned `agent.completed` in one global conversation | Current integrated controlled cohort; prior aggregate: 32/32 completed invocations | Live evidence created on `00039-joh`; current production `00042-rob` | `conversations`, `conversation_messages`, `agent_invocations` | **Planned** 0:20–0:50 |
| The assistant response is a live Gemini invocation | [`PERSONAL_AGENT_MODEL_AUTH_REPORT.md`](PERSONAL_AGENT_MODEL_AUTH_REPORT.md), [`MODEL_VERIFICATION.md`](MODEL_VERIFICATION.md) | Inspect provenance badge/audit and correlate invocation to Cloud Logging | Example persisted invocation IDs are listed in the model-auth report; V1 run suffixes listed below | Live evidence `00039-joh`; current production `00042-rob`; earlier model proof `00024-nef` | `agent_invocations`, `agent_tool_calls` | **Planned** 0:35–0:50 and 3:42–3:50 |
| ADK session state persists across turns and refresh | [`REAL_AGENT_RESPONSE_PROVENANCE.md`](REAL_AGENT_RESPONSE_PROVENANCE.md), [`REAL_AGENT_DRIVEN_MULTI_USER_E2E.md`](REAL_AGENT_DRIVEN_MULTI_USER_E2E.md) | Send a follow-up in the same chat; reload bootstrap; compare `adk_session_id` | Two-turn integrated cohort PASS; historical two-user run in the E2E report | Live evidence created on `00039-joh`; current production `00042-rob` | `adk_sessions`, `adk_session_events`, `agent_invocations` | **Planned** 0:20–0:50 |
| The Agent drafts a privacy-aware Post from conversation | [`V1_PRODUCT_COMPLETION_MATRIX.md`](V1_PRODUCT_COMPLETION_MATRIX.md), [`REAL_AGENT_DRIVEN_MULTI_USER_E2E.md`](REAL_AGENT_DRIVEN_MULTI_USER_E2E.md) | Live Personal Agent selects task/draft tools; user reviews the inline draft | `multi-20260901-0357`, `multi-final-20260901-0420`, `multi-true-peer-20260901-0435` | `00035-beq` evidence; integrated UI on `00039-joh` | `task_workspaces`, `intent_private_data`, `intent_posts`, `agent_tool_calls`, `presentation_directives` | **Planned** 0:50–1:15 |
| Publishing changes authoritative state and makes an eligible Post discoverable | [`V1_LIVE_ACCEPTANCE_REPORT.md`](V1_LIVE_ACCEPTANCE_REPORT.md), [`V1_PRODUCT_COMPLETION_MATRIX.md`](V1_PRODUCT_COMPLETION_MATRIX.md) | Publish through authenticated API/UI; reload; open Explore detail | Three V1 multi-intent runs; current integrated requester Post | `00035-beq`; current UI `00039-joh` | `intent_posts`, `events`, `community_memberships` | **Planned** 0:58–1:15 |
| Background work continues without the requester keeping the UI open | [`V1_PRODUCT_COMPLETION_MATRIX.md`](V1_PRODUCT_COMPLETION_MATRIX.md), [`V1_LIVE_ACCEPTANCE_REPORT.md`](V1_LIVE_ACCEPTANCE_REPORT.md) | Publish a later compatible Post; inspect Pub/Sub push/reconciliation and refreshed candidates | All three multi-intent runs; production event consumption HTTP 200 | `00035-beq`; worker targets the canonical production URL | `events`, `execution_leases`, `candidate_assessments`, `candidate_rank_events` | **Planned** 2:15–2:35 |
| One request can evaluate multiple independently owned candidate Agents | [`V1_LIVE_ACCEPTANCE_REPORT.md`](V1_LIVE_ACCEPTANCE_REPORT.md), [`V1_PRODUCT_COMPLETION_MATRIX.md`](V1_PRODUCT_COMPLETION_MATRIX.md) | Inspect candidate list and separate Agent Rooms | Judge cohort: 3 ranked candidates and separate Agent Rooms; V1 gates: 4 candidates per requester scenario | Final production; V1 evidence `00035-beq` | `candidate_assessments`, `coordination_rooms`, `room_participants` | **Planned** 1:15–1:35 |
| Agent-to-Agent negotiation is real, scoped and model-generated | [`REAL_AGENT_DRIVEN_MULTI_USER_E2E.md`](REAL_AGENT_DRIVEN_MULTI_USER_E2E.md), [`V1_LIVE_ACCEPTANCE_REPORT.md`](V1_LIVE_ACCEPTANCE_REPORT.md) | Inspect distinct A2A invocation/session IDs and room messages; call official A2A 1.0 Agent Cards | A2A turn/invocation/session IDs in E2E report; three direct production A2A calls HTTP 200 | Orchestrator `00035-beq`; Peer `00022-seh` | `a2a_turns`, `agent_invocations`, `adk_sessions`, `room_messages` | **Planned** 1:25–1:50 |
| Candidate ordering changes when evidence changes | [`V1_PRODUCT_COMPLETION_MATRIX.md`](V1_PRODUCT_COMPLETION_MATRIX.md), [`V1_LIVE_ACCEPTANCE_REPORT.md`](V1_LIVE_ACCEPTANCE_REPORT.md) | Compare current assessments with immutable rank events before/after later Post/evidence | Four rank-change events observed in V1 live gate; current cohort has 3 ranked candidates | `00035-beq`; visible on `00039-joh` | `candidate_assessments`, `candidate_rank_events` | **Planned** 1:35–1:50 and 2:15–2:35 |
| Private instructions and contact data are not published or sent to peers | [`V1_LIVE_ACCEPTANCE_REPORT.md`](V1_LIVE_ACCEPTANCE_REPORT.md), [`AUTHORIZATION_MATRIX.md`](AUTHORIZATION_MATRIX.md) | Insert unique private canary; inspect public projection and A2A transcript | Canary absent in every multi-intent run | `00035-beq`; controls retained in `00039-joh` | `intent_private_data` versus `intent_posts`; `room_messages`; `contact_cards` | **Planned** 1:50–2:15 |
| Cross-user private reads are denied | [`AUTHORIZATION_MATRIX.md`](AUTHORIZATION_MATRIX.md), [`REAL_AGENT_DRIVEN_MULTI_USER_E2E.md`](REAL_AGENT_DRIVEN_MULTI_USER_E2E.md) | Authenticated owner A requests owner B's task/conversation | HTTP 403 in every V1 scenario and the two-user live E2E | `00035-beq`; historical `00024-nef` | Authorization check precedes private collection reads; denied request in Cloud Logging | Not shown; report/callout only |
| Both humans must approve the same current proposal version | [`V1_LIVE_ACCEPTANCE_REPORT.md`](V1_LIVE_ACCEPTANCE_REPORT.md), [`REAL_AGENT_DRIVEN_MULTI_USER_E2E.md`](REAL_AGENT_DRIVEN_MULTI_USER_E2E.md) | First approval returns waiting; second independent approval commits | 15/15 live dual-approved matches across three V1 runs | `00035-beq` | `proposals`, `proposal_acceptances`, `human_approvals`, `holds` | **Planned** 2:35–3:05 |
| Match commit is atomic and occurs once | [`V1_PRODUCT_COMPLETION_MATRIX.md`](V1_PRODUCT_COMPLETION_MATRIX.md), [`DEPLOYMENT_VERIFICATION.md`](DEPLOYMENT_VERIFICATION.md) | Re-submit approval; verify one Match/Room and unchanged counts | 15 V1 matches; current integrated cohort: 1 match | `00035-beq`; visible on `00039-joh` | `matches`, `intent_posts`, `proposals`, `holds`, `coordination_rooms` | **Planned** 2:55–3:12 |
| The shared human room unlocks only after the Match | [`REAL_AGENT_DRIVEN_MULTI_USER_E2E.md`](REAL_AGENT_DRIVEN_MULTI_USER_E2E.md), [`V1_PRODUCT_COMPLETION_MATRIX.md`](V1_PRODUCT_COMPLETION_MATRIX.md) | Inspect locked candidate room before approval and shared room after commit | 15 unlocked shared rooms in V1; current cohort includes a simulated participant message | `00035-beq`; visible on `00039-joh` | `coordination_rooms`, `room_participants`, `room_messages` | **Planned** 3:05–3:18 |
| A committed outcome updates the relationship network | [`V1_PRODUCT_COMPLETION_MATRIX.md`](V1_PRODUCT_COMPLETION_MATRIX.md), [`V1_LIVE_ACCEPTANCE_REPORT.md`](V1_LIVE_ACCEPTANCE_REPORT.md) | Open Network after Match/outcome and inspect provenance | Current integrated cohort: 1 relationship | `00039-joh`; V1 behavior proven on `00035-beq` | `relationships`, `relationship_events`, `outcomes` | **Planned** 3:18–3:24 |
| Global memory requires explicit user confirmation | [`V1_PRODUCT_COMPLETION_MATRIX.md`](V1_PRODUCT_COMPLETION_MATRIX.md), [`V1_LIVE_ACCEPTANCE_REPORT.md`](V1_LIVE_ACCEPTANCE_REPORT.md) | Verify proposed memory is excluded; confirm; inspect retrieval | Current integrated cohort: 1 confirmed memory; V1 proposed/confirmed gate PASS | `00039-joh`; V1 evidence `00035-beq` | `memories`, `events` | **Planned** 3:24–3:30 |

## Named acceptance runs

- `multi-20260901-0357` — PASS
- `multi-final-20260901-0420` — PASS
- `multi-true-peer-20260901-0435` — PASS
- Current integrated controlled requester cohort — PASS; the script does not
  assign a separate persisted run ID, so this document does not invent one.

## Evidence handling

- The video must hide email addresses, passwords, Firebase tokens, private
  instructions and private contact fields.
- Firestore screenshots should show collection and document type plus a
  non-sensitive correlation ID; do not open raw identity or token documents.
- The final video file and timestamps remain pending human recording. Replace
  **planned** with actual timestamps only after reviewing the exported video.
