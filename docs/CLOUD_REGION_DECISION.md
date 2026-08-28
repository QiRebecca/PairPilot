# Cloud region decision

Decision recorded 2026-08-28 after checking the current official model and
Firestore location documentation.

## Decision

| Workload | Location | Reason |
|---|---|---|
| Gemini inference | `global` | Gemini 3.7 Flash is GA and officially supports the global endpoint; global is the documented quickstart path and lowest-cost serving tier. |
| Cloud Run services | `europe-west2` | London is close to the UK-based developer, supports Cloud Run, and co-locates application compute with Firestore. |
| Firestore Native | `europe-west2` | London is an officially supported regional Firestore location; regional storage reduces write latency and cost for this bounded demo. |
| Artifact Registry | `europe-west2` | Co-location with Cloud Run avoids unnecessary cross-region image transfer. |
| Pub/Sub | Google-managed global service | Topics remain in the project; subscribers call the London Cloud Run workers with authenticated push. |

## Why not a single location for everything?

The selected current model, `gemini-3.7-flash`, exposes `global`, `us`, and
`eu` model availability rather than a London regional model endpoint. The
official developer guide uses `global`, so PairPilot uses that endpoint and
keeps stateful application resources in London.

## Firestore irreversibility check

Before database creation, `gcloud firestore locations list` returned
`europe-west2` with display name London. The resulting default database was
then verified as `FIRESTORE_NATIVE`, Standard edition, in `europe-west2`.

## Sources

- [Gemini 3.7 Flash model page](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-7-flash)
- [Gemini 3.7 Flash developer guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/guides/gemini-3-7-flash)
- [Firestore locations](https://docs.cloud.google.com/firestore/docs/locations)

