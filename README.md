# PairPilot

**The relationship layer for personal agents.**

PairPilot gives every person a persistent personal agent that autonomously
communicates and negotiates with other personal agents to form real-world
plans, using past relationships as social memory and escalating only the final
irreversible commitment to the human.

[Open the public live demo](https://pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app)

Track: **Taskmaster** · Exact live model: **`gemini-3.7-flash`** · Built from
scratch for the Google All Things Agentic Hackathon.

## Problem

Finding a conference roommate is not a search result. It is a social workflow:
discover people, decide whom to trust, ask sensitive compatibility questions,
negotiate dates and cost, track changing state, and know when to ask the human.
Today's assistants leave the user doing that coordination across messages.

## Why this is not a chatbot

The interface is a live relationship network, not a chat box. The human enters
one goal. A Google ADK personal agent then chooses tools, uses a prior
relationship, discovers open agents, sends authenticated A2A messages, records
beliefs with provenance, calculates a deterministic compromise, negotiates a
versioned proposal, places a hold, and stops at an effect-level approval
boundary. Infrastructure—not peer text or the model—controls authority.

## Taskmaster alignment

PairPilot completes an autonomous, multi-step real-world workflow. Three fresh
deployed evaluations finished in 73.422, 42.351, and 47.250 seconds, with zero
private-memory leakage and zero unauthorized commitment. The third run selected
a different valid action trajectory. See [the evaluation](docs/EVAL_REPORT.md).

## Product workflow

1. Qi expresses one natural-language ICML roommate goal.
2. Qi Agent inspects a trusted prior relationship with Alice Agent.
3. It discovers open-network candidates and asks Alice for an introduction.
4. It contacts model-selected candidates concurrently over A2A.
5. It treats peer claims as reports, not truth, and records dispositions.
6. A deterministic tool computes that three shared nights add `$62`, below the
   delegated `$70` ceiling.
7. Qi and Maya agents accept the exact proposal version.
8. Infrastructure places a temporary hold and displays the full effect
   contract.
9. Only the human can approve. Commit revalidates every current authority fact.
10. After approval, one atomic Firestore commit creates the match,
    relationship provenance, Alice introduction credit, and scoped memory.

## Agent architecture

- **Qi Agent:** a live Google ADK coordinator with typed, authorized tools.
- **Alice Agent:** an independent ADK personal agent with introduction
  authority and its own scoped context.
- **Maya and Lena Agents:** independent ADK peers that answer minimum-necessary
  questions and decide on proposal versions for their owners.
- **Authority layer:** deterministic privacy, proposal, hold, availability,
  approval, idempotency, and commit checks.

The source contains world facts and permission boundaries, not a semantic demo
sequence. Gemini chooses contact order, tool use, questions, dispositions,
proposal timing, and observable recommendation text.

## Agent-to-agent communication

The private peer service exposes separate official A2A 1.0 Agent Cards and
JSON-RPC endpoints for Alice, Maya, and Lena. The public orchestrator calls it
with a short-lived Google-signed identity token under a least-privilege Cloud
Run service account. Typed envelopes bind run, session, sender, recipient,
speech act, claims, proposal version, and expiry. See
[the A2A report](docs/A2A_SPIKE_REPORT.md).

## Relational memory network

Firestore stores relationships separately from messages, beliefs, proposals,
holds, approvals, matches, and memories. Every relationship update includes
provenance event IDs. Reset restores only seeded world facts; it never seeds a
successful trajectory. Current availability and commitment state always come
from authoritative documents, never semantic memory.

## Google technology usage

- Vertex AI global endpoint with the verified GA model
  **`gemini-3.7-flash`**.
- Google Agent Development Kit **2.8.0** for Qi, Alice, Maya, and Lena agents.
- A2A Python SDK **1.1.2**, JSON-RPC protocol **1.0**.
- Cloud Run for the public orchestrator/UI and authenticated peer service.
- Firestore Native in `europe-west2` for truth, provenance, and outbox state.
- Pub/Sub for durable observable domain events.
- Artifact Registry, Cloud Build, IAM, and Cloud Logging.

Live mode is pinned. There is no silent fallback to an older model or a
scripted response. [Model evidence](docs/MODEL_VERIFICATION.md) records the
endpoint, location, SDK metadata, and authenticated test calls.

## Privacy model

Each personal agent receives only its owner-scoped context. Qi's protected raw
fact is never included in peer prompts or the public API; only a minimum-
necessary preference is disclosed. A typed guard checks prohibited raw text,
memory references, sensitivity, and necessity before outbound A2A. Peer
messages are untrusted data and cannot grant tools, read private memory, alter
authority, or create approval.

## Approval and commitment model

The approval card shows identity, shared/solo dates, cost, terms, uncertainty,
recommendation, disclosure scope, proposal version, hold expiry, and current
availability. The endpoint requires `APPROVE VERSION N` for that exact version.
Immediately before commit it revalidates proposal/hold expiry, availability,
both agent acceptances, disclosure hash, human approval version, and
idempotency. No valid current approval means no match.

## Local setup

Prerequisites: Python 3.12, Node 24, Google Cloud CLI, and Application Default
Credentials for the dedicated project.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip==26.2.1
.venv/bin/python -m pip install -e services/orchestrator -e services/peer_agents
.venv/bin/python -m pip install -r requirements-dev.txt
npm --prefix web ci
gcloud auth application-default login
export PYTHONPATH="$PWD/packages/schemas:$PWD/services/orchestrator:$PWD/services/peer_agents"
make lint typecheck test
make dev
```

The local API uses ADC and a short-lived identity token; no API key or service
account key is required. Copy `.env.example` only for non-secret local settings.

## Google Cloud setup

Use a dedicated billed project and explicitly review billing, budget, and
Firestore location before running the idempotent bootstrap:

```bash
export GOOGLE_CLOUD_PROJECT=your-dedicated-project
export PAIRPILOT_REGION=europe-west2
make bootstrap PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
make seed PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
```

`infra/bootstrap_gcp.sh` intentionally does not create or change a billing
link, budget, or Firestore location without an owner decision.

## Environment variables

| Variable | Purpose |
|---|---|
| `GOOGLE_CLOUD_PROJECT` | Dedicated Google Cloud project; required |
| `GOOGLE_CLOUD_LOCATION` | Vertex location; `global` in live deployment |
| `PAIRPILOT_MODEL_ID` | Pinned live model; `gemini-3.7-flash` |
| `PAIRPILOT_PEER_BASE_URL` | Authenticated private peer Cloud Run URL |
| `PAIRPILOT_PUBLIC_BASE_URL` | Canonical public HTTPS URL for metadata |
| `PAIRPILOT_PERSIST_PROVENANCE` | Enables peer Firestore provenance |

`PAIRPILOT_PEER_ID_TOKEN` exists only for a short-lived local test injection;
Cloud Run obtains an identity token from its metadata identity.

## Deployment

```bash
make deploy PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
make verify PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
```

The script builds immutable images in Cloud Build, deploys scale-to-zero
services, keeps peers authenticated, grants only the runtime identity peer
invocation, and prints the public URL. Current verified resources are documented
in [deployment verification](docs/DEPLOYMENT_VERIFICATION.md).

## Seed and reset

```bash
make seed PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
make reset PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
```

Reset requires an exact project confirmation and deletes only 17 explicit
mutable collections. Identities, private profiles, availability, metadata, and
the public quota ledger are protected. The seed contains facts only—no messages,
beliefs, proposals, holds, approvals, matches, runs, or success events.

## Tests

```bash
make lint
make typecheck
make test
make test-live PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
make submission-check
```

The suite covers privacy isolation, prompt injection, peer claim provenance,
approval/version/hold/availability rules, atomic commit and idempotency,
bounded termination, A2A routes, public API redaction, reset protection, and
the live A2A exchange.

## Evaluation

Three fresh public Cloud Run runs, each following Reset, reached the current
human approval boundary inside 90 seconds. No run leaked the protected phrase,
wrote an approval, or committed a match. Run IDs, model turns, tool calls,
messages, latency, and captured token metadata are in
[docs/EVAL_REPORT.md](docs/EVAL_REPORT.md).

## Known limitations

- A positive deployed commit requires a real person to approve the visible
  unexpired contract. We do not impersonate that action in automation.
- Immediate A2A task state is in memory; durable business provenance is in
  Firestore.
- The public safe demo allows one live run at a time and 12 run starts per UTC
  day. Cloud Run is capped at one instance.
- Synthetic demo identities and availability are not real bookings or identity
  verification.
- Cloud Trace and optional managed Memory Bank were not added; they are not
  claimed.

## Prior-work disclosure

The product concept was explored before the hackathon, but no earlier source
code was reused. The complete disclosure is in [PRIOR_WORK.md](PRIOR_WORK.md).

## Repository map

```text
packages/schemas/       typed domain and A2A contracts
services/orchestrator/  Qi ADK agent, workflow, authority, public API
services/peer_agents/   independent Alice, Maya, Lena ADK/A2A service
web/                    React/TypeScript relationship-network UI
infra/                  bootstrap, seed/reset, build, deploy, verify
tests/                  unit and live integration evidence
docs/                   model, cloud, A2A, evaluation, compliance reports
```
