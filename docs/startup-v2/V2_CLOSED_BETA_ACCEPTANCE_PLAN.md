# Startup V2 closed-beta acceptance plan

Updated: 2026-09-01

Status: `PARTIAL`

Phase 11 has fail-closed candidate isolation, a repeatable ten-user cohort seeder,
and live bounded acceptance. Core multi-user, security, load, Agent-to-Agent,
approval, outcome and persistent-chat gates have passed. The status remains partial
until all named failure-injection, offline, visual and accessibility gates pass.

## Isolation contract

The same Google Cloud project is retained, but Startup V2 candidate state uses:

- Firestore physical collection prefix: `candidate_v2_`;
- event topic: `pairpilot-v2-candidate-events`;
- push subscription: `pairpilot-v2-candidate-worker`;
- dead-letter topic: `pairpilot-v2-candidate-dlq`;
- Cloud Run no-traffic tag: `startup-v2-candidate`;
- logical document namespace: `candidate`.

`Settings` refuses to start a non-production environment without an explicit,
validated collection prefix. `GoogleCloudStore` applies the prefix at every read,
query, create, update, transaction document name, and list boundary. Candidate
outbox events publish only to the candidate topic.

The candidate middleware returns 404 for old `/api/demo`, `/api/os`, and
`/api/intents` surfaces. This prevents historical public demo routes from reading
candidate collections outside the authenticated V2 product plane.

## Controlled cohort

`scripts/seed_startup_v2_candidate_cohort.py` plans or creates:

- ten independent Firebase Authentication users;
- clearly labelled controlled identities;
- passwords stored only in Secret Manager;
- three exact controlled Communities: AI Conference, University Orientation,
  and Local Weekend Activities;
- 25 Posts and Requests;
- all five supported task types;
- idempotent reuse of existing tasks by deterministic title;
- no hardcoded candidate rankings, Agent conversations, proposals, approvals,
  Matches, or outcomes.

The script refuses to write unless the URL contains the candidate tag, health
reports `environment=candidate`, and the exact operator confirmation is present.
Its `--plan` mode is non-mutating and currently passes locally.

## Acceptance driver

`scripts/run_startup_v2_candidate_acceptance.py` is designed to:

1. sign in all ten controlled users from Secret Manager;
2. verify the 25-Post, five-task-type, three-Community inventory;
3. verify cross-user task IDOR denial;
4. verify candidate legacy demo surfaces are disabled;
5. verify Explore does not expose login email or owner UID;
6. run 80 concurrent authenticated non-model bootstrap requests;
7. create 20 clearly sourced mixed-state candidate memories for volume testing;
8. discover compatible task pairs from authoritative state;
9. contact eight peer Agents through the generic runtime;
10. require seven exact-version dual approvals;
11. complete four Matches and cancel three to exercise recovery.

The driver never writes assessments, Agent messages, proposals, approvals,
Matches, or relationship outcomes directly. Those must emerge from generic
runtime and server-authoritative routes.

## Local verification

- Python suite: 163 passed; zero failed; dependency deprecation warnings only.
- Candidate isolation/config tests: passed.
- Candidate seeder plan: passed.
- Candidate deploy shell syntax: passed.
- Full frontend suite from Phase 10: 9 passed and production build passed.

## Live candidate evidence

- Candidate revision: `pairpilot-orchestrator-00053-suw` at zero production traffic.
- Immutable image digest:
  `sha256:04500d3320139300b2e07200643fdca952dfd67bb58c77f3b27937c313cae6a3`.
- Candidate health: `environment=candidate`, live
  `gemini-3.7-flash`, Google ADK and A2A runtime.
- Cohort: 10 Firebase users, 3 Communities, 25 Requests, 25 OPEN Posts and all
  5 supported task types.
- Security/load run `v2-acceptance-1788273643`: cross-user task 403, legacy
  surface 404, no Explore owner/email leak, 80 requests at concurrency 20 with
  zero failures in 20.55 seconds.
- Agent lifecycle run `v2-acceptance-1788273819`: 8 candidate Agent Rooms,
  7 dual-approved committed Matches, 4 completed and 3 cancelled.
- A2A evidence: 18 completed `gemini-3.7-flash` turns, 23,392 input tokens,
  2,978 output tokens, zero candidate Agent job failures and zero candidate DLQ
  records at the evidence snapshot.
- Persistent Agent run `v2-acceptance-1788276697`: one
  `GLOBAL_PERSONAL_AGENT` conversation completed draft, revise and explicit publish
  turns; all three invocation records are `COMPLETED`, the private draft was read
  back, and the authoritative Post is OPEN.
- A post-tool Gemini 429 was reproduced on revision `00052`, persisted honestly,
  fixed with bounded retries plus explicitly classified authoritative-tool recovery,
  and reaccepted on revision `00053` without clearing the conversation history.
- Production remained `pairpilot-orchestrator-00050-qiq` at 100% throughout.

## Gates still required

- Add duplicate delivery, worker crash/lease expiry, transaction conflict, expiry,
  orphan Room, saved-search and SSE reconnect failure injection.
- Complete the remaining named lifecycle scenarios, including Community leave/rules,
  Room channel transitions, Match change/reapproval/calendar/contact/backup,
  Connection reuse, scoped Memory, Decisions/Notifications, autonomy and moderation.
- Perform authenticated visual/accessibility acceptance with independent users.
