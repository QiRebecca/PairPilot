# Deployment verification

Latest verification: 2026-08-29. The detailed migration history and rollback
commands are in `docs/INTENT_LAYER_DEPLOYMENT_REPORT.md`.

## Public demo

`https://pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app`

No login is required. Anonymous production requests returned HTTP 200 for `/`,
`/api/health`, `/api/demo/state`, and `/og.png`. The health response reported
`LIVE GEMINI + GOOGLE ADK + A2A` and exact model `gemini-3.7-flash`.

## Current Cloud Run evidence

| Service | Access | 100% revision | Image digest |
|---|---|---|---|
| `pairpilot-orchestrator` | public | `pairpilot-orchestrator-00009-poy` | `sha256:b1204b4a3a00729b47298a646325f5731bfbcc8d1ca6a26dc78d37238f8c9132` |
| `pairpilot-peer-agents` | authenticated only | `pairpilot-peer-agents-00013-yem` | `sha256:3ebca863c7a73ea40fb7eb5817a8c9723f7495b14b052dc106ee5104c4a783f1` |

The previous `pairpilot-orchestrator-00005-lbc` and
`pairpilot-peer-agents-00009-8l4` revisions were not deleted and remain exact
rollback targets. `intent-v2` tagged URLs remain available for both final
revisions.

## Functional verification

| Verification | Result |
|---|---|
| Empty reset → live draft → review → publish | Pass |
| Maya/Lena OPEN intent registry, Qi initially empty | Pass |
| Authenticated intent-scoped A2A | Pass |
| Three live runs inside the 90-second bound | Pass |
| Distinct direct and warm-introduction trajectories | Pass |
| Public/agent-only/protected redaction | Pass |
| 15-minute intent-capacity hold and exact approval | Pass |
| Real human positive commit | Pass |
| Both posts MATCHED and competitor session released | Pass |
| Relationship, conditional Alice credit, scoped memory | Pass |
| Duplicate approval returned original result with unchanged counts | Pass |
| Production refresh preserved committed match | Pass |
| Matched posts absent from OPEN registry | Pass |
| Pub/Sub-backed durable outbox/events | Pass |
| Production dependency audits | Pass |

Verified positive run: `47fc6638-e2b5-4253-8b5c-bee46e07278d`.
Verified match: `0a8a2e2e-ff84-415a-8d34-a881675215eb`.
