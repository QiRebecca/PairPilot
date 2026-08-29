# PairPilot multi-user migration audit

Status: Stage 1 baseline audit, 2026-08-29  
Project: `pairpilot-agentic-ecb84a`  
Protected source tag: `pre-multi-user-beta-a8eff6e`  
Implementation branch: `multi-user-public-beta`

## Executive finding

The current production-oriented code is a strong single-owner Personal Agent demo, not a multi-user application. It must not be described as a public beta. Authentication, ownership, isolation, generic peer loading, asynchronous work, and dual human authority are absent from the production path.

The safe migration is additive: preserve the current walkthrough in an explicitly synthetic demo namespace, add a new authenticated `/api/app/*` plane, verify it with two independent Firebase principals, and promote only the no-traffic candidate after the P0 gate passes.

## Current global and synthetic assumptions

| Area | Current evidence | Risk | Required replacement |
| --- | --- | --- | --- |
| Active owner | `qi-agent` and `qi-owner` are hard-coded in web, OS, workflow, schemas, commit, and UI code | Every browser operates the same identity | Verified Firebase UID mapped to one stored Personal Agent |
| Global conversation | `GLOBAL_CONVERSATION_ID` and one Qi conversation | Cross-user transcript disclosure | Deterministic per-UID conversation with ownership checks |
| Global run | `_run_lock` in `web.py` | Unrelated users block each other | Per-task execution lease and per-user quota |
| Global public state | `public_state()` lists shared collections and selects one run | Cross-user state and event leakage | UID-scoped bootstrap plus redacted public projections |
| Global reset | unauthenticated `/api/demo/reset` deletes and reseeds workflow collections | Destructive cross-user action | Demo-only namespace reset; no production reset |
| Shared quotas | process/IP request counters and one daily run count | No per-user spend control | Verified UID, task, contact, endpoint and IP-hash quotas |
| Synthetic peers | Alice, Maya and Lena cards/routes are fixed | Cannot represent registered users | Generic Personal Agent loader by stored agent ID |
| One-sided approval | one `approvals/{proposal_id}` record, producer `human-user` | Either party is absent from authority | Approval keyed by proposal/version/approving UID; require both owners |
| Qi-specific commit | commit looks for `qi-agent`, candidate, and Qi-Alice relationship | Candidate-specific and impersonable | Source/target agents and owners loaded from authoritative intents |
| Shared result records | match, relationship, memory are authored for Qi | Wrong owner and privacy scope | Participant UIDs, two relationship projections, owner-scoped memory |
| Public/private intent | private and public data are separately stored in some paths, but shared APIs aggregate them around Qi | Backend can return the wrong owner's record | `intent_posts` public projection plus owner-only `intent_private_data` |
| Event stream | one unauthenticated SSE stream drives a synchronous run | Event leakage and long request | Authenticated task/inbox stream and Pub/Sub bounded turns |

## Endpoint audit

The following current routes are unauthenticated and therefore demo-only until retired or replaced:

- `POST /api/intents/draft`
- `GET /api/intents/{intent_id}/review`
- `GET /api/os/bootstrap`
- `POST /api/os/messages`
- `GET /api/os/tasks/{task_id}`
- `POST /api/os/rooms/{room_id}/mode`
- `POST /api/os/rooms/{room_id}/messages`
- `POST /api/os/memories/{memory_id}`
- `POST /api/intents/publish`
- `GET /api/intents/open`
- `GET /api/intents/{intent_id}`
- `GET /api/demo/run/stream`
- `POST /api/demo/reset`
- `POST /api/demo/revalidate`
- `POST /api/demo/approve`
- `POST /api/demo/reject`

`GET /api/health` may remain public with non-sensitive output. The new public surface may additionally expose Firebase web configuration, redacted discovery, Terms, Privacy, and isolated demo data.

## Firestore collection audit

Existing workflow collections include `runs`, `intents`, `intent_private_data`, `intent_pair_sessions`, `agent_turns`, `agent_messages`, `beliefs`, `proposals`, `proposal_acceptances`, `holds`, `approval_requests`, `approvals`, `matches`, `relationships`, `relationship_events`, `memories`, `events`, and Personal Agent OS projections.

Problems:

1. many documents have only Agent IDs and no authoritative owner UID;
2. collection scans are bounded globally rather than queried by owner or participant;
3. server credentials bypass Firestore client rules, so route authorization is the actual boundary;
4. synthetic records are not namespaced strongly enough for a public feed;
5. approval identity is not represented;
6. room membership uses Agent IDs but not authoritative participant UIDs;
7. schema-version fields are inconsistent.

New production collections will use schema version `2` and include:

- `users`, `personal_agents`, `user_privacy_configs`, `user_autonomy_configs`, `usage_quotas`, `user_namespaces`;
- owner-scoped `task_workspaces`, `conversations`, `conversation_messages`, `intent_private_data`, `candidate_assessments`, `memories`, and `decisions`;
- redacted `intent_posts` public projections;
- participant-scoped `coordination_rooms`, `room_participants`, `room_messages`, `proposals`, `proposal_acceptances`, `human_approvals`, `holds`, `matches`, and `relationships`;
- `blocks`, `reports`, `execution_leases`, and `audit_events`.

## Authorization invariants

The backend derives identity only from a verified Firebase ID token. It never accepts `uid`, `owner_uid`, `email`, or `agent_id` in a browser body as authority.

Every protected handler uses centralized checks for authentication, verified email where required, resource ownership, room/match participation, demo namespace, and administrative action. Missing or invalid authentication returns 401; authenticated non-membership returns 403 without revealing private resource details.

## Migration and rollback design

1. Keep tag `pre-multi-user-beta-a8eff6e` and the current demo revision for rollback.
2. Add v2 schema fields and new collections; do not rewrite current synthetic documents in place.
3. Put synthetic walkthrough data under an explicit demo namespace and persistent UI label.
4. Register Firebase Authentication in the existing project; use web config only in the browser and ADC on Cloud Run.
5. Deploy candidate revisions with tag `multi-user-beta` and zero production traffic.
6. Create two controlled, verified test users without writing credentials to source, docs, or logs.
7. Run the dual-user E2E and IDOR matrix before any traffic change.
8. If the gate fails, remove the candidate tag or route it to zero; production remains on the protected revision.

## Stage 1 acceptance

- Baseline source protected by tag and branch.
- Shared identity, state, lock, reset, stream, peer and approval assumptions identified.
- Non-destructive additive migration chosen.
- Multi-user completion is explicitly not claimed.

