# Deployment verification

Verification date: 2026-08-28.

## Public demo

Public URL:

```text
https://pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app
```

No login is required. Anonymous requests returned HTTP 200 for `/`,
`/api/health`, `/api/demo/state`, `/og.png`, and the complete
`/api/demo/run/stream` SSE execution.

## Cloud Run evidence

| Service | Access | Ready revision | Image digest |
|---|---|---|---|
| `pairpilot-orchestrator` | public | `pairpilot-orchestrator-00005-lbc` | `sha256:83126090503f41cb9e4e7ee2a7cc939be849e4b351a89b9e31ba96f996aa74d0` |
| `pairpilot-peer-agents` | authenticated only | `pairpilot-peer-agents-00009-8l4` | `sha256:a8427f1fd37da1640457016d8c94e040ef5aa856e82a07bad80b7ee8af1ef593` |

The orchestrator revision uses the user-managed runtime service account, 1
vCPU, 1 GiB, concurrency 4, maximum scale 1, minimum scale 0, a 120-second HTTP
request bound around the 90-second decision bound, and HTTP startup/liveness
probes on `/api/health`. The private peer grants `roles/run.invoker` to only the
runtime service account used here; no service-account key or API key exists.

Cloud Builds `15ee8cb3-a6d3-426b-8182-cae36277529c` and
`e9e8cfca-7f02-4806-af42-7db1dd496954` built the current public and peer
images successfully after the security dependency update. The earlier
`web-001` build failure is retained in history: it correctly rejected a
non-installable schema path. `web-002` fixed the container layout; later
revisions added canonical HTTPS metadata and the persistent public quota
ledger.

Cloud Build `47f161d5-8754-4100-b259-1dd7aa69dd20` then launched both exact
image digests and ran `pip-audit 2.10.1`. Both steps reported no known
vulnerabilities. The frontend lockfile separately reports zero vulnerabilities
from `npm audit --audit-level=high`.

## Functional verification

| Verification | Direct evidence | Result |
|---|---|---|
| Public URL loads | anonymous HTML title and production JS/CSS returned | Pass |
| No login required | no auth header/cookie used by curl | Pass |
| Accurate live badge | `/api/health` returns exact model and execution mode | Pass |
| Reset works | mutable run/proposal/hold/events deleted; facts reseeded | Pass |
| Live run starts | public SSE emitted `started`, changing snapshots, `complete` | Pass |
| Private peer auth works | public run received Alice/Maya/Lena A2A responses | Pass |
| Approval pause works | three deployed runs ended `WAITING_FOR_HUMAN_APPROVAL` | Pass |
| No unauthorized commit | zero approvals and zero matches after all eval runs | Pass |
| Firestore persists | reload returned turns, messages, proposal, hold, contract | Pass |
| Pub/Sub outbox works | run 1 flushed 18 durable events | Pass |
| Public quota survives reset | protected `demo_quota` count advanced from 1 to 2 | Pass |
| Private data not exposed | API omits private profiles; message leak check false | Pass |
| Social preview works | `/og.png` is PNG; metadata uses canonical HTTPS URL | Pass |
| Cloud logs correlate | revision log contains reset, SSE, state, probe HTTP 200s | Pass |
| Production dependencies | exact deployed image digests audited in Cloud Build | Pass |

The deployed evaluation run IDs and full metrics are in `docs/EVAL_REPORT.md`.
The first post-deploy state probe exceeded its original 30-second network
window after the health endpoint succeeded. The verification script now allows
two bounded retries within a 60-second request window; the immediate rerun
passed all anonymous endpoints and both 100%-traffic revision checks.

## Pending human-operated check

The positive commit path cannot be truthfully completed without a human
approving the current visible effect contract. The button and endpoint are
deployed. Tests and a live negative call prove that an absent, stale, expired,
or mismatched approval cannot commit. After a real approval, verify the match,
new Maya relationship, Alice introduction counter, scoped memory, refresh
persistence, and idempotent duplicate click.
