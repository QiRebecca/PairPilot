# Startup V2 closed-beta acceptance plan

Updated: 2026-09-01

Status: `PARTIAL`

Phase 11 now has fail-closed candidate isolation, a repeatable ten-user cohort
seeder, and a bounded acceptance driver. The candidate has not yet been deployed
or seeded, so no live scenario is claimed as passed.

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

- Python suite: 161 passed; zero failed; dependency deprecation warnings only.
- Candidate isolation/config tests: passed.
- Candidate seeder plan: passed.
- Candidate deploy shell syntax: passed.
- Full frontend suite from Phase 10: 9 passed and production build passed.

## Gates still required

- Deploy the immutable no-traffic candidate revision.
- Create and verify candidate Pub/Sub/DLQ topology and OIDC push delivery.
- Seed the cohort and retain its content-free run evidence.
- Run the complete driver and the ten required scenario-specific assertions.
- Add duplicate delivery, worker crash/lease expiry, transaction conflict, expiry,
  orphan Room, saved-search and SSE reconnect failure injection.
- Run bounded live-Gemini semantic acceptance separately from non-model load.
- Perform authenticated visual/accessibility acceptance with independent users.
