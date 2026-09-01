# PairPilot Startup V2 current-state audit

Updated: 2026-09-01 (Asia/Shanghai)

## Executive finding

PairPilot is a deployed, authenticated multi-user V1 with a real Gemini/ADK
Personal Agent, A2A worker, public Post projections, candidate assessments,
Rooms, dual approval, Matches, Relationships, and user-controlled Memory.
It is not yet Startup V2. The primary risk is inconsistent lifecycle semantics
across a large production dataset, followed by incomplete route-level product
surfaces and incomplete background-monitoring acceptance.

## Submission protection and source control

- Submitted commit: `7d3d6f6f4b830688e7d522c2a9517cf8833d27ae`.
- Permanent tag: `hackathon-submission-final`.
- Original submission tag: `all-things-agentic-submission-v1`.
- Preserved submitted orchestrator revision: `pairpilot-orchestrator-00045-tig`.
- Submitted image digest: `sha256:4aded86e939fe18e8beffa9d9a1a2ee731436cb8509c6d5631252e7123e2fb1a`.
- Startup branch: `startup-v2`.
- First V2 commit: `50b1f79` (`fix: stabilize persistent personal agent turns`).
- Remote: `https://github.com/QiRebecca/PairPilot.git`.
- No Startup V2 commit has been pushed during this audit.

Production rollback:

```bash
gcloud run services update-traffic pairpilot-orchestrator \
  --project pairpilot-agentic-ecb84a \
  --region europe-west2 \
  --to-revisions pairpilot-orchestrator-00045-tig=100
```

Return to the current stable revision:

```bash
gcloud run services update-traffic pairpilot-orchestrator \
  --project pairpilot-agentic-ecb84a \
  --region europe-west2 \
  --to-revisions pairpilot-orchestrator-00050-qiq=100
```

## Live infrastructure

| Surface | Current state |
|---|---|
| Project | `pairpilot-agentic-ecb84a` |
| Region | `europe-west2` |
| Production URL | `https://pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app/` |
| Orchestrator | `pairpilot-orchestrator-00050-qiq`, 100% traffic |
| Orchestrator digest | `sha256:8023ad23b8b9a4bd77e397682ccf96e02a8dfd0e88293bba0a17a72274d32d35` |
| Orchestrator bounds | max 20 instances, concurrency 16, timeout 180s |
| Peer service | `pairpilot-peer-agents-00022-seh` |
| Model | `gemini-3.7-flash`, Vertex AI global endpoint |
| Google ADK | `2.8.0` |
| Google Gen AI SDK | `2.20.0` |
| A2A SDK | `1.1.2` |
| Firebase Admin | `7.5.0` |
| Event topic | `pairpilot-events` |
| Worker subscription | `pairpilot-multi-user-worker`, push + OIDC |
| DLQ | `pairpilot-events-dead-letter`, max 5 deliveries |
| Audit subscription | `pairpilot-events-audit` |
| Composite Firestore indexes | none configured |
| Browser Firestore access | denied; Cloud Run APIs are authoritative |

The push subscription targets the current production URL and runtime service
account. Candidate-specific Pub/Sub isolation does not yet exist.

## Identity and production data inventory

The privacy-safe inventory script is `scripts/startup_v2_inventory.py`. It emits
only aggregate counts and never prints emails, UIDs, tokens, or document content.

| Measure | Count |
|---|---:|
| Firebase Authentication users | 89 |
| Verified Firebase users | 89 |
| Clearly labelled controlled accounts | 14 |
| Firestore top-level collections | 63 |
| `users` | 90 |
| `personal_agents` | 89 |
| `task_workspaces` | 90 |
| `intent_posts` | 84 |
| Open Posts | 24 |
| Matched Posts | 52 |
| Coordination Rooms | 114 |
| Matches | 26 |
| Relationships | 42 |
| Memories | 68 |
| Candidate assessments | 170 |
| Candidate rank events | 246 |
| Notifications | 358 |
| A2A turns | 256 |
| ADK sessions | 221 |
| Agent invocations | 95 |
| Recorded job failures | 42 |

Production already exceeds the requested closed-beta volume, but only 14 Auth
accounts are clearly labelled as controlled. Counts alone are not acceptance
evidence.

Identity Platform email/password sign-in is enabled and passwords are required.
MFA is currently disabled. Six authorized domains are configured.

The production push worker had zero undelivered messages during the audit. The
pull audit subscription had 222 undelivered messages, and the DLQ inspection
subscription had 25, with oldest messages older than eleven hours. Those pull
subscriptions are not user-facing delivery paths, but the DLQ backlog is an
unresolved operational signal and must be classified before Phase 9 can pass.

## Schema and lifecycle gaps

1. `intent_posts` is a correct public projection collection and
   `intent_private_data` is the corresponding owner-private collection. They
   should be evolved, not duplicated under new names.
2. Post statuses currently include `OPEN`, `MATCHED`, `AWAITING_APPROVAL`, and
   `CLOSED`; the full V2 state machine is not implemented.
3. Nine Posts and ten Tasks still use legacy type `peer_coordination`; eight
   Posts and nine Tasks still use `conference_room_share`.
4. Rooms use legacy `ACTIVE` and `NEEDS_INPUT` rather than the required V2 room
   lifecycle.
5. All 26 Match documents lack a normalized V2 `status` field.
6. Relationship documents lack a normalized Connection status model.
7. Memories mix `status` and `confirmation_status`, and do not yet expose V2
   type, usage provenance, sensitivity, or contradiction handling.
8. Two candidate assessments, two Rooms, two Relationships, and one Task have
   no production namespace value and require classification before migration.
9. `proposal_versions` contains only one document while 29 proposals exist;
   proposal version history is not consistently materialized.
10. There is no schema migration registry, export-before-migration workflow, or
    candidate namespace migration runner.
11. The only project bucket is the US multi-region Cloud Build source bucket; no
    dedicated europe-west2 Firestore export bucket or retention policy exists.

## Current authenticated UI

Implemented routes:

- `/app/agent`
- `/app/requests`
- `/app/requests/:taskId`
- `/app/explore`
- `/app/communities`
- `/app/rooms`
- `/app/rooms/:roomId`
- `/app/matches`
- `/app/network`
- `/app/memory`
- `/app/notifications`
- `/app/settings`
- `/app/admin`

Missing direct product routes include Post Detail, Community Detail, Match
Detail, Connections list/detail, Decision Inbox, Autonomy Center, and Audit.
Most authenticated UI remains in one `BetaApp.tsx`, which blocks independent
route evolution and makes visual/recovery testing unnecessarily broad.

## Current Agent and authority model

The live Personal Agent has real typed tools for task creation, task and decision
inspection, Post draft/revision/publication/status, public Post search, candidate
inspection, A2A contact, Room opening, candidate assessment, proposal creation,
revalidation, withdrawal, relationship inspection, Memory proposal/inspection,
and presentation directives.

Strong invariants already exist:

- Firebase principal ownership checks;
- deny-all direct Firestore browser rules;
- public/private Post separation;
- participant-scoped Rooms and contact cards;
- exact proposal version approval;
- dual-human approval before Match commitment;
- no fabricated assistant fallback on model failure;
- private instructions cannot be written into the Agents-only transcript;
- duplicate Pub/Sub delivery is idempotent;
- peer claims are not upgraded to verified facts.

Missing V2 tools or incomplete behavior include saved Posts/searches, search
monitoring, counter-proposals, Connection reuse and introduction, Memory usage
events, action-specific autonomy, Community Agent, Match changes/cancellation,
calendar export, backup activation, and typed route-level entity presentation.

## Reliability and recent failures

The current revision fixed the production failure where persisted `null` task
IDs became the string `"None"`, and fixed task creation choosing a Community the
user had not joined. Real multi-user Agent acceptance passed after the fix.
Historical revisions contain Vertex 429s, unsupported intent types, Community
membership failures, and ADK/OpenTelemetry context cleanup errors. Current
revision logs had no severity-ERROR entries during the stabilization acceptance,
but a sustained SLO and retry classification do not yet exist.

## Test baseline

- Python: 103 tests collected; the latest complete run passed all 103.
- Frontend: 7 Vitest tests passed.
- Frontend lint, TypeScript checking, and production build passed.
- Existing live acceptance covers real Gemini, multiple Firebase principals,
  A2A contact, ranking, dual approval, Match, Room, Relationship, and Memory.
- It does not prove every Startup V2 browser route, offline monitoring, migration,
  moderation, load, or recovery acceptance gate.

## Phase 0 conclusion

The correct path is an additive, versioned migration over the existing public and
private collections. Replacing the database or creating parallel meanings would
increase privacy and consistency risk. Production must remain on the current V1
schema until a no-traffic candidate, dry-run migration, controlled-user
acceptance, and rollback evidence exist.
