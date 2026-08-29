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
| `pairpilot-orchestrator` | public | `pairpilot-orchestrator-00011-xeg` | `sha256:148afd80cc32dec4c02620f81271b1a745d7cd8cecd0c3491bd7860d4a2879a6` |
| `pairpilot-peer-agents` | authenticated only | `pairpilot-peer-agents-00013-yem` | `sha256:3ebca863c7a73ea40fb7eb5817a8c9723f7495b14b052dc106ee5104c4a783f1` |

The user-journey follow-up revision makes the new-request entry visible from a
persisted matched state and automatically starts coordination after publish.
It was first verified at the zero-traffic `user-ui` tag, then routed to 100%.
The intent-layer revision `pairpilot-orchestrator-00009-poy`, original baseline
`pairpilot-orchestrator-00005-lbc`, and previous peer revision were not deleted
and remain rollback targets.

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
