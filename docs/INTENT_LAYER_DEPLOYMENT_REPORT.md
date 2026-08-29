# Intent layer deployment report

Status: **PRODUCTION MIGRATION VERIFIED** on 2026-08-29.

## Protected baseline

- Baseline commit: `9930444`.
- Rollback tag: `pre-intent-marketplace-9930444`.
- Previous orchestrator: `pairpilot-orchestrator-00005-lbc`.
- Previous peer service: `pairpilot-peer-agents-00009-8l4`.
- Both previous revisions remained at 100% production traffic throughout
  implementation, migration, tagged tests, three approval-boundary evaluations,
  and the human positive commit.

## Final revisions

| Evidence | Peer agents | Orchestrator |
|---|---|---|
| Final revision | `pairpilot-peer-agents-00013-yem` | `pairpilot-orchestrator-00009-poy` |
| Image digest | `sha256:3ebca863c7a73ea40fb7eb5817a8c9723f7495b14b052dc106ee5104c4a783f1` | `sha256:b1204b4a3a00729b47298a646325f5731bfbcc8d1ca6a26dc78d37238f8c9132` |
| Tagged URL | `https://intent-v2---pairpilot-peer-agents-ew4hz5g3la-nw.a.run.app` | `https://intent-v2---pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app` |
| Authentication | runtime identity / Cloud Run Invoker | public UI/API |
| Final traffic | 100% | 100% |

The canonical public URL remains:
`https://pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app`.

## Migration

The tagged orchestrator ran the idempotent reset/backfill against the existing
Firestore database. It deleted only explicit mutable workflow collections and
reseeded identities, availability, base relationships, Maya/Lena `OPEN` posts,
and owner-private peer contexts. Verification immediately afterward showed:

- Qi active intent: none;
- OPEN owners: Maya and Lena;
- messages/proposals/holds/approvals/matches/memories: all zero;
- public state contained no `intent_private` or private profiles.

## Verification gates

- Local submission check: Ruff, ESLint, strict mypy across 40 source files,
  TypeScript, 48 Python unit tests, React test, Vite build, diff/secret scan.
- Dependency audit: npm production vulnerabilities `0`; Python audit `0` after
  installing the already-pinned `cryptography 50.0.0`; `pip check` clean.
- Live isolated A2A integration: passed against Vertex AI.
- Tagged health, public redaction, OG asset, service identity, and model/config
  checks: passed.
- Three fresh tagged composer→draft→publish→A2A→approval-boundary runs: passed;
  see `docs/INTENT_LAYER_EVAL_REPORT.md`.
- Real human-approved positive commit and duplicate replay: passed; see
  `docs/POSITIVE_COMMIT_VERIFICATION.md`.
- Post-migration production verification: health/model badge, state redaction,
  OG, both 100% traffic routes, and persisted committed match all passed.

## Issues found under tagged traffic

Tagged live testing found and fixed, without production impact:

1. Cloud Run tagged peer URLs require the canonical service URL as ID-token
   audience.
2. The live model can use `roommate` as a harmless synonym for the registered
   `conference_room_share` type.
3. Peer structured output can be empty; peers now retry the schema-bounded live
   turn without a scripted fallback.
4. Alice model claims are normalized from validated top-level introduction
   fields so a declined introduction cannot leave a stale one-sided target.
5. A failed peer in a two-post batch no longer discards another peer's valid
   evidence; the model receives a bounded per-intent recovery result.
6. Duplicate human approval now returns the original committed effect instead
   of a misleading conflict.

## Traffic migration and rollback

Traffic was migrated only after every P0 gate and positive commit passed:

```bash
gcloud run services update-traffic pairpilot-peer-agents \
  --project pairpilot-agentic-ecb84a --region europe-west2 \
  --to-revisions pairpilot-peer-agents-00013-yem=100
gcloud run services update-traffic pairpilot-orchestrator \
  --project pairpilot-agentic-ecb84a --region europe-west2 \
  --to-revisions pairpilot-orchestrator-00009-poy=100
```

Exact rollback commands, if needed:

```bash
gcloud run services update-traffic pairpilot-peer-agents \
  --project pairpilot-agentic-ecb84a --region europe-west2 \
  --to-revisions pairpilot-peer-agents-00009-8l4=100
gcloud run services update-traffic pairpilot-orchestrator \
  --project pairpilot-agentic-ecb84a --region europe-west2 \
  --to-revisions pairpilot-orchestrator-00005-lbc=100
```

No old revision was deleted.
