# A2A spike report

Status: **verified locally and on private Cloud Run** on 2026-08-28.

This spike proves a live Qi Google ADK agent can choose a legitimate tool that
resolves a remote Agent Card, sends an official A2A v1 message, receives an
independently generated Alice ADK response, and persists its provenance.

## Versions

| Component | Exact version |
|---|---:|
| Python | 3.12.6 |
| Google ADK | 2.8.0 |
| A2A Python SDK | 1.1.2 with `http-server` extra |
| Google Gen AI SDK | 2.20.0 |
| Gemini model | `gemini-3.7-flash` |
| A2A binding | JSON-RPC, protocol version 1.0 |

Versions were verified from installed package metadata and imported APIs, not
copied from an older tutorial.

## Architecture proved

```text
Local Qi Agent (Google ADK + live Gemini 3.7 Flash)
    -> model selects request_warm_introduction
    -> authenticated GET /.well-known/agent-card.json
    -> official A2A JSON-RPC 1.0 POST /a2a/alice
Private pairpilot-peer-agents Cloud Run revision
    -> Alice Agent (separate Google ADK agent/session/context/tool)
    -> live Gemini 3.7 Flash structured decision
    -> A2A Message response
    -> immutable provenance document in Firestore
```

## Remote Agent Card

Endpoint:

```text
https://pairpilot-peer-agents-ew4hz5g3la-nw.a.run.app/.well-known/agent-card.json
```

Verified fields:

```json
{
  "name": "Alice Personal Agent",
  "version": "0.1.0",
  "supportedInterfaces": [
    {
      "url": "https://pairpilot-peer-agents-ew4hz5g3la-nw.a.run.app/a2a/alice",
      "protocolBinding": "JSONRPC",
      "protocolVersion": "1.0"
    }
  ],
  "capabilities": {"streaming": false},
  "skills": [{"id": "trusted-introduction"}]
}
```

The service is private. Requests require a short-lived Google-signed identity
token and Cloud Run Invoker authorization; there is no API key or service
account JSON key.

## Model-selected Qi action

Qi received only the high-level roommate goal. The live model selected:

```json
{
  "name": "request_warm_introduction",
  "args": {
    "request_summary": "Looking for a verified female roommate for ICML in Seoul (July 6-10) with quiet overnight compatibility."
  }
}
```

The private sleep fact was neither in Qi's outbound argument nor in Alice's
message. The tool, not the model, enforced the typed A2A envelope and authenticated
transport.

## Cloud request and response

Sanitized request evidence:

```json
{
  "message_id": "d1885ada-19ec-42d0-8365-5bc0c6107333",
  "from_agent_id": "qi-agent",
  "to_agent_id": "alice-agent",
  "speech_act": "INTRODUCTION_REQUEST"
}
```

Alice's live response:

```json
{
  "message_id": "32457d1e-285b-4411-81d8-bd45a7be71ea",
  "decision": "OFFER_INTRODUCTION",
  "natural_language": "I would be glad to connect you with Maya, who is attending ICML and also looking for a quiet overnight environment.",
  "reason": "Maya matches the requested criteria for ICML attendance and quiet preferences, and the requesting agent has a reliable coordination history.",
  "confidence": 0.95
}
```

The exact wording is model-generated; it is not present in source or seed data.
Alice called her own scoped relationship-context tool before producing the
structured response.

## Persistence and Cloud evidence

| Evidence | Verified value |
|---|---|
| Cloud Run service | `pairpilot-peer-agents` |
| Ready revision | `pairpilot-peer-agents-00003-dt2` |
| Region | `europe-west2` |
| Cloud Build ID | `57402e36-8d1c-4bc4-b8aa-c1a6c5ac6624` |
| Image digest | `sha256:af799e14476164aa02b59a2cf5c75b9f7b69359caddeaeb3a50c145f8b99dabb` |
| Firestore collection | `a2a_spike_provenance` |
| Provenance document | `32457d1e-285b-4411-81d8-bd45a7be71ea` |
| Response SHA-256 | `26bc90f7d77a4947aef981b3ae7fe1381f74c8473e8483d5844e3d590dd32c47` |
| Exact persisted model | `gemini-3.7-flash` |

Cloud Logging recorded an authenticated `GET /.well-known/agent-card.json` and
`POST /a2a/alice` with HTTP 200 on the same revision. The Firestore document
records matching inbound/outbound message IDs, protocol, agent identities,
model ID, timestamp, and response hash.

## Local verification

The integration test uses the real A2A route, resolver, client factory,
protobuf messages, Alice ADK runner, and live Gemini model through an ASGI
transport. It passed in 9.52 seconds:

```text
tests/integration/test_a2a_live_spike.py::
test_qi_reads_card_and_sends_live_a2a_message PASSED
```

Local spike provenance uses an in-memory adapter to make assertions. The Cloud
Run runtime uses the Firestore adapter and fails closed if persistence fails.

## Known limitations

- This bounded spike exposes only Alice's card; Maya and Lena cards are part of
  the full peer-agent implementation gate.
- The A2A task store is in-memory because the spike uses the immediate-message
  workflow; business provenance is persisted in Firestore.
- A2A SDK 1.1.2 currently emits protobuf field-label deprecation warnings during
  validation. They do not change the v1 exchange result.
- The orchestrator side ran locally with ADC for this proof. The remote peer ran
  on Cloud Run with the user-managed runtime service account. The production
  orchestrator Cloud Run deployment remains pending.

## Verification status

- Official A2A Agent Card: **verified**.
- Official A2A JSON-RPC v1 message: **verified**.
- Independent remote ADK agent: **verified**.
- Live eligible Gemini response: **verified**.
- Authenticated private Cloud Run endpoint: **verified**.
- Firestore provenance: **verified**.
- Full three-peer production workflow: **pending**.
