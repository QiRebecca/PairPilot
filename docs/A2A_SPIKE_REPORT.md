# A2A implementation report

Status: **verified locally and on private Cloud Run** on 2026-08-28.

The initial Alice spike is now a three-peer implementation. A live Qi Google
ADK client resolves independent Agent Cards, sends official A2A v1 messages,
receives independently generated Alice, Maya, and Lena ADK responses, and
persists per-agent provenance.

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
Qi Agent (Google ADK + live Gemini 3.7 Flash)
    -> resolves /.well-known/agents/{agent-id}.json
    -> authenticated A2A JSON-RPC 1.0 POST /a2a/{alice|maya|lena}
Private pairpilot-peer-agents Cloud Run revision
    -> separate Alice, Maya, and Lena ADK definitions
    -> separate scoped context tools, sessions, owners, and stores
    -> live Gemini 3.7 Flash PeerDecision
    -> validated A2AMessageEnvelope response
    -> immutable per-agent provenance document in Firestore
```

## Remote Agent Card

Card endpoints:

```text
https://pairpilot-peer-agents-ew4hz5g3la-nw.a.run.app/.well-known/agents/alice-agent.json
https://pairpilot-peer-agents-ew4hz5g3la-nw.a.run.app/.well-known/agents/maya-agent.json
https://pairpilot-peer-agents-ew4hz5g3la-nw.a.run.app/.well-known/agents/lena-agent.json
```

Verified fields:

```json
{
  "name": "Maya Personal Agent",
  "version": "0.2.0",
  "supportedInterfaces": [
    {
      "url": "https://pairpilot-peer-agents-ew4hz5g3la-nw.a.run.app/a2a/maya",
      "protocolBinding": "JSONRPC",
      "protocolVersion": "1.0"
    }
  ],
  "capabilities": {"streaming": false},
  "skills": [{"id": "roommate-coordination"}]
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

## Cloud peer matrix

The original four-peer-exchange matrix ran on revision
`pairpilot-peer-agents-00004-nz2`. The current production revision is
`pairpilot-peer-agents-00009-8l4`; deployed orchestrator evaluation runs then
repeated Alice, Maya, and Lena exchanges through the same cards and routes.
The output below records protocol fields only; natural-language content was
model-generated and is not seeded in source.

| Peer | Request | Response | Validated claim fields | Proposal binding |
|---|---|---|---|---|
| Alice | `INTRODUCTION_REQUEST` | `INTRODUCTION_RESPONSE` | `introduction_decision` | none |
| Maya | `INFORMATION_REQUEST` | `INFORMATION_RESPONSE` | overnight routine and availability | none |
| Lena | `INFORMATION_REQUEST` | `INFORMATION_RESPONSE` | overnight routine and availability | none |
| Maya | version-1 `PROPOSAL` | `ACCEPTANCE` | proposal version and availability | version 1 echoed |

The executor validates the inbound envelope and destination, rejects expired
messages, runs the addressed agent's isolated ADK session, validates its
`PeerDecision`, assigns peer-report provenance to claims, and creates a new
validated outbound envelope. The canonical claim value is derived from the
model's enumerated action; it does not choose the outcome for the model.

## Persistence and Cloud evidence

| Evidence | Verified value |
|---|---|
| Cloud Run service | `pairpilot-peer-agents` |
| Ready revision | `pairpilot-peer-agents-00009-8l4` |
| Region | `europe-west2` |
| Cloud Build ID | `e9e8cfca-7f02-4806-af42-7db1dd496954` |
| Image digest | `sha256:a8427f1fd37da1640457016d8c94e040ef5aa856e82a07bad80b7ee8af1ef593` |
| Firestore collection | `a2a_spike_provenance` |
| Provenance documents | Four outbound-message-ID documents from the peer matrix |
| Response SHA-256 | A 64-character digest persisted for every response |
| Exact persisted model | `gemini-3.7-flash` |

Cloud Logging recorded authenticated HTTP 200 POSTs to `/a2a/alice`,
`/a2a/maya`, `/a2a/lena`, and `/a2a/maya` on the same revision. Safe Firestore
read-back confirmed that each document records the correct peer identity,
`qi-agent` destination, A2A/JSON-RPC/1.0, exact model, and a 64-character hash.

## Local verification

The integration test uses the real A2A route, resolver, client factory,
protobuf messages, Alice ADK runner, and live Gemini model through an ASGI
transport. The unit suite currently reports 34 passing tests; the live A2A
integration test also passes against Vertex. Ruff and strict mypy pass.

```text
tests/integration/test_a2a_live_spike.py::
test_qi_reads_card_and_sends_live_a2a_message PASSED
```

Local spike provenance uses an in-memory adapter to make assertions. The Cloud
Run runtime uses the Firestore adapter and fails closed if persistence fails.

## Known limitations

- The A2A task stores are in-memory because this implementation uses immediate-message
  workflow; business provenance is persisted in Firestore.
- A2A SDK 1.1.2 currently emits protobuf field-label deprecation warnings during
  validation. They do not change the v1 exchange result.
- The current public orchestrator invokes this private service with its
  user-managed runtime identity. Peer task state remains in memory for the
  immediate-message exchange; business messages and provenance are durable.

## Verification status

- Official A2A Agent Card: **verified**.
- Official A2A JSON-RPC v1 message: **verified**.
- Independent remote ADK agent: **verified**.
- Live eligible Gemini response: **verified**.
- Authenticated private Cloud Run endpoint: **verified**.
- Firestore provenance: **verified**.
- Three independent peer cards and endpoints: **verified**.
- Full deployed orchestrator golden path: **verified**.
