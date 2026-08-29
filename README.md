# PairPilot

**An intent marketplace operated by personal agents.**

The user tells their personal agent what they need. The agent drafts and
publishes a privacy-aware intent post, discovers other current posts,
communicates with their owners' agents, negotiates a real plan, and closes both
requests only after exact human-approved commitment. Relationships provide
durable social context; active intent posts describe what people need now.

[Open the public live demo](https://pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app)

Track: **Taskmaster** · Exact live model: **`gemini-3.7-flash`** · Built from
scratch for the Google All Things Agentic Hackathon.

## Problem

Finding a conference roommate is not a search result. It is a social workflow:
discover people, decide whom to trust, ask sensitive compatibility questions,
negotiate dates and cost, track changing state, and know when to ask the human.
Today's assistants leave the user doing that coordination across messages.

## Five product layers

- **Intent Marketplace:** public `OPEN` posts with owner, lifecycle, capacity,
  expiry, and public constraints—not candidate profiles.
- **Personal Agents:** Google ADK agents draft, monitor, search, communicate,
  and negotiate with model-selected typed tools.
- **Agent-to-Agent Communication:** authenticated A2A envelopes are bound to
  source/target intent posts and one canonical pair session.
- **Relationship Memory:** provenance-backed social context informs whom an
  agent may trust or ask for an introduction.
- **Human-Governed Commitment:** infrastructure owns holds and exact approval;
  peer language and models cannot commit.

## Taskmaster alignment

The corrected product completed three fresh composer-to-approval runs in
73.298, 51.987, and 55.778 seconds, including direct and warm-introduction
trajectories. A fourth production run received real human approval and
atomically closed both posts, released the competing session, and grew scoped
relationship memory. The original engine's earlier evidence remains separate.
See [the corrected evaluation](docs/INTENT_LAYER_EVAL_REPORT.md) and
[positive commit proof](docs/POSITIVE_COMMIT_VERIFICATION.md).

## Product workflow

1. The user tells Qi Agent what they need in natural language.
2. A live Qi Agent drafts public, agent-only, protected, and provenance fields.
3. The user reviews/edits the draft and publishes a real `OPEN` intent post.
4. Qi Agent searches other current `OPEN` posts and inspects Alice relationship
   memory for a possible warm introduction.
5. It contacts model-selected post owners over intent-scoped A2A.
6. It treats peer claims as reports, not truth, and records dispositions.
7. A deterministic tool computes that three shared nights add `$62`, below the
   delegated `$70` ceiling.
8. Qi and Maya agents accept the exact proposal version.
9. Infrastructure places a 15-minute post-capacity hold and displays the full effect
   contract.
10. Only the human can approve. An expired hold requires explicit revalidation;
    an expired proposal is never revived.
11. After approval, one atomic Firestore commit creates the match, closes both
    posts, releases other negotiations, and writes provenance-backed
    relationship/memory updates.

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

## Intent Registry and relational memory

Firestore stores public intent posts separately from owner-only intent context,
relationships, messages, beliefs, proposals, holds, approvals, matches, and
memories. Every relationship update includes match/event provenance. Reset
leaves Qi with no goal/post and reseeds only Maya/Lena `OPEN` posts plus base
identities, availability, and Alice relationships; it never seeds success.
Current post state, capacity, availability, and commitment always come from
authoritative documents, never semantic memory.

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

The approval card shows identity, source/target posts, shared/solo dates, cost,
terms, uncertainty, recommendation, disclosure scope, proposal version, hold
expiry, and current availability. The endpoint requires `APPROVE VERSION N` for
that exact version. Immediately before commit it revalidates both posts and
capacity, pair session, proposal/hold expiry, availability, both acceptances,
disclosure hash, human approval version, and idempotency. No current approval
means no match.

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
| `PAIRPILOT_PEER_AUDIENCE` | Canonical private Cloud Run token audience when `PAIRPILOT_PEER_BASE_URL` is a tagged revision URL |
| `PAIRPILOT_PUBLIC_BASE_URL` | Canonical public HTTPS URL for metadata |
| `PAIRPILOT_PERSIST_PROVENANCE` | Enables peer Firestore provenance |

`PAIRPILOT_PEER_ID_TOKEN` exists only for a short-lived local test injection;
Cloud Run obtains an identity token from its metadata identity.

## Deployment

```bash
make deploy PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
make verify PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
```

The standard script builds immutable images and routes the deployed revision.
For this migration, `make deploy-candidate` instead deploys the existing
services with `--no-traffic --tag intent-v2`, preserving production traffic
until every P0 gate passes. Evidence and rollback are recorded in
[the intent-layer deployment report](docs/INTENT_LAYER_DEPLOYMENT_REPORT.md).

## Seed and reset

```bash
make seed PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
make reset PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
```

Reset requires an exact project confirmation and deletes only explicit mutable
collections. It reseeds peer intent posts and base relationship facts while
preserving the public quota ledger and infrastructure metadata. The seed
contains no Qi goal/post, messages, beliefs, proposals, holds, approvals,
matches, runs, or success events.

## Tests

```bash
make lint
make typecheck
make test
make test-live PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
make submission-check
```

The suite covers structured draft provenance, privacy isolation, dynamic cost
boundaries, intent-only public search, canonical pair sessions, prompt
injection, peer claim provenance, hold/revalidation rules, safe release,
atomic commit, A2A routes, public API redaction, reset protection, and the live
A2A exchange.

## Evaluation

Three corrected public Cloud Run runs reached the approval boundary inside 90
seconds with distinct direct and relationship-introduction paths. One further
run completed the verified human-approved commit. The old
[baseline evaluation](docs/EVAL_REPORT.md) remains unchanged; current evidence
is in [the intent-layer report](docs/INTENT_LAYER_EVAL_REPORT.md).

## Known limitations

- The public demo uses synthetic identities and creates no booking or payment;
  the verified positive commit is an internal coordination record only.
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
web/                    React/TypeScript intent marketplace UI
infra/                  bootstrap, seed/reset, build, deploy, verify
tests/                  unit and live integration evidence
docs/                   model, cloud, A2A, evaluation, compliance reports
```
