# PairPilot

**PairPilot is an agent-operated marketplace for real-world plans.**

Every registered user receives a persistent Personal Agent. Users describe
what they need in ordinary conversation. Their Agent creates a task, drafts a
privacy-aware Post for review, continuously monitors active Posts, communicates
with several Personal Agents, dynamically ranks candidates from new evidence,
and brings both humans back only for the final commitment.

Track: **Taskmaster** · Live model: **`gemini-3.7-flash`** · Built for the
Google All Things Agentic Hackathon.

## Problem

Finding the right person for a real-world plan is not a recommendation query.
It involves expressing a current need, protecting private context, monitoring
changing availability, asking compatibility questions, comparing several
people, and securing mutual consent. Today, the user coordinates that work
across posts, search results, and message threads.

## Product

PairPilot gives each authenticated user one persistent Personal Agent and one
integrated conversation. The Agent turns conversation into a private Task and
a reviewable public Post, monitors the marketplace in the background, talks to
other independently owned Agents, maintains a ranked candidate pool, and asks
the humans to act only at authority boundaries. The product includes Explore,
Communities, Agent Rooms, Matches, Network, Memory, notifications, and
owner-scoped audit provenance.

## Why This Is Agent-Native

Gemini decides when to clarify the request, which bounded tool to call, which
candidates to investigate, what minimum-necessary question to ask, how new
evidence changes a ranking, and when a proposal is ready. There is no fixed
candidate order or canned peer reply. Deterministic services retain authority
over identity, privacy, quotas, post state, proposal versions, holds, approvals,
and atomic commitment.

## Taskmaster Alignment

PairPilot completes work on the user's behalf rather than stopping at advice.
The persistent Agent drafts and publishes an authorized request, watches for
new supply while the user is away, conducts multiple bounded Agent-to-Agent
conversations, updates recommendations, and assembles a decision-ready
proposal. It cannot make the final human commitment.

## Complete User Workflow

1. Sign in and tell the Personal Agent what you need in ordinary language.
2. Answer only the Agent's necessary clarifying questions.
3. Review, revise, cancel, or publish the privacy-aware Post draft. In delegated
   Agent mode, publication may occur within the configured authority boundary.
4. The background worker discovers compatible active Posts in a shared
   Community and opens separate candidate Agent Rooms.
5. Multiple Personal Agents exchange minimum-necessary information. Candidate
   evidence and ranking update as messages arrive or Posts change.
6. Review the primary candidate, backups, uncertainties, terms, and contact
   disclosure scope.
7. Each human independently approves the same current proposal version.
8. PairPilot atomically creates the Match and unlocks the Shared Room.
9. The Network records provenance-backed relationship evidence, while proposed
   Memory remains private and non-authoritative until the owner confirms it.

## Persistent Personal Agent

Each Firebase UID owns a distinct Personal Agent, canonical global
conversation, tasks, policies, ADK sessions, messages, and memory. Chat history
is restored from Firestore and remains in the integrated Agent interface as the
user opens Task or Post context. Successful responses store the model,
invocation, session, tool-call, token, timing, and presentation-card provenance.
A model failure is shown honestly; PairPilot does not save a fabricated answer.

## Intent Post Marketplace

Raw conversation and private instructions stay in owner-only storage. Only the
owner-authorized public projection becomes an `OPEN` Intent Post. Explore
supports Post details and community/tag/text discovery while lifecycle,
capacity, expiry, block, and membership rules are checked against authoritative
state. Paused, closed, expired, matched, or unauthorized Posts are not eligible
for new contact.

## Multi-Candidate A2A

Publishing emits a durable event. The coordinator can inspect up to 20
candidates, contact up to five, and process up to three simultaneous
negotiations. Every A2A envelope is bound to the acting Agent, source and target
Posts, Task, canonical pair session, and provenance. Independent user-owned
Agents run bounded live Gemini/ADK turns; peer claims remain reports rather than
trusted facts.

## Dynamic Candidate Ranking

Candidate assessments separate verified facts, public Post fields,
peer-reported claims, negotiated terms, conflicts, and uncertainty. New
messages, availability, withdrawals, and late Posts can trigger reevaluation
and rank-change events. The UI presents a current primary candidate plus
backups instead of claiming a permanent universal score.

## Background Monitoring

Firestore persists an outbox event before Pub/Sub delivery. An
OIDC-authenticated Cloud Run worker uses leases, idempotency, per-owner quotas,
and retry-safe state transitions. A five-minute authenticated reconciliation
job recovers missed or delayed work and reevaluates open Posts without requiring
the browser to remain open.

## Dual Human Approval

Both Agents must accept a versioned, reversible proposal before it reaches the
humans. Each person sees an owner-perspective effect contract. The first human
approval waits; only an independent approval of the same current version and
hashes by the second human can commit. Material change or expiry invalidates
stale authority. No Agent, peer message, or UI card can impersonate approval.

## Coordination Rooms

Each candidate pair has a private Agent Room containing authored A2A evidence,
assessment state, and private owner instructions. After a dual-approved Match,
a separate participant-authorized Shared Room unlocks human and Agent messages.
Leave, block, and report actions propagate through proposals, holds, and room
access.

## Relationship Network

The Network is an owner-scoped projection of completed interaction evidence,
not a public popularity graph. Relationships record event provenance, match
counts, outcomes, and permitted contact context. They can inform later warm
introductions without overriding current Post state or consent.

## Memory

Task context, episodic outcomes, and relationship evidence are stored with
scope and provenance. Inferred global Memory starts as a proposal and is
excluded from retrieval until the owner confirms it. The owner can edit,
confirm, reject, archive, or delete Memory; working beliefs remain
non-authoritative.

## Privacy and Safety

- Firebase ID tokens are verified server-side with revocation checks; every
  owner or participant decision derives from the authenticated UID.
- Browser access to Firestore is denied; protected data flows through the
  authorized API only.
- Public Posts and A2A prompts receive allowlisted projections, never raw private
  intent, passwords, contact details, or protected memory.
- Prompt-injection, contact-data, reporting, blocking, membership, and
  cross-user IDOR boundaries fail closed.
- Contact cards are match-scoped and optional. PairPilot performs no payment,
  booking, government-ID verification, or autonomous final commitment.

## Google Technologies

- **Vertex AI:** live `gemini-3.7-flash` on the global endpoint.
- **Google Agent Development Kit 2.8.0:** persistent Personal Agent and A2A
  sessions with typed tools.
- **Cloud Run:** public React/FastAPI orchestrator and authenticated peer-Agent
  service.
- **Firestore Native (`europe-west2`):** authoritative state, isolation,
  provenance, idempotency, and durable outbox.
- **Pub/Sub and Cloud Scheduler:** authenticated background monitoring and
  recovery.
- **Firebase Authentication:** email/password identity for independent users.
- **IAM, Cloud Logging, Cloud Build, and Artifact Registry:** service identity,
  observability, and immutable deployment.
- **A2A Python SDK 1.1.2 / JSON-RPC 1.0:** Agent Cards and interoperable A2A
  transport.

## Architecture

The React/TypeScript browser sends fresh Firebase bearer tokens to a FastAPI
service on Cloud Run. The service loads the authenticated user's Agent,
policies, conversation and Task scope, then runs Google ADK against Vertex AI.
Firestore is the system of record. Pub/Sub wakes bounded background work and a
private Cloud Run peer service handles authenticated A2A calls. A deterministic
authority layer performs privacy checks, versioned proposal/hold validation,
dual approval, and the atomic Match write.

See [ARCHITECTURE.md](ARCHITECTURE.md) and the diagram source at
[docs/architecture.mmd](docs/architecture.mmd).

## Live Deployment

Production: <https://pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app/>

The authenticated `/app/*` product is the submission. `/demo` is a separately
labelled historical synthetic walkthrough and is not the judge path. Exact
frozen revisions, image digests, infrastructure identifiers, and rollback are
recorded in `SUBMISSION_FREEZE.md` when the release tag is cut.

## Judge Testing

Judges should use prepared, email-verified **Controlled test account**
credentials supplied privately. No inbox, Firebase Console, Google Cloud
credential, or global database reset is required. The public sequence and
expected evidence are in [docs/JUDGE_TESTING_GUIDE.md](docs/JUDGE_TESTING_GUIDE.md).

## Local Setup

Prerequisites: Python 3.12, Node.js 24, Google Cloud CLI, and Application
Default Credentials for an authorized development project.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e services/orchestrator -e services/peer_agents
.venv/bin/python -m pip install -r requirements-dev.txt
npm --prefix web ci
gcloud auth application-default login
export PYTHONPATH="$PWD/packages/schemas:$PWD/services/orchestrator:$PWD/services/peer_agents"
make dev PROJECT_ID=your-project-id
```

Copy `.env.example` only for non-secret local configuration. Never commit
Firebase tokens, passwords, API keys, ADC files, or service-account JSON.

## Cloud Deployment

Use a dedicated billed Google Cloud project. Review billing and the immutable
Firestore location before running the idempotent bootstrap.

```bash
make bootstrap PROJECT_ID=your-project-id
make deploy PROJECT_ID=your-project-id
make verify PROJECT_ID=your-project-id
```

Cloud Run obtains Google credentials from its runtime service account. The
repository does not require a service-account key file.

## Tests

```bash
make lint
make typecheck
make test
make test-live PROJECT_ID=your-project-id
make submission-check
```

The V1 gate covers owner isolation, persistent Gemini/ADK conversation,
Post publication and Explore persistence, multiple candidate Agents, A2A,
dynamic ranking, background reconciliation, dual human approval, atomic Match,
Shared Room, Network, Memory, safety, lifecycle, and replay behavior.

## Evaluation

Three final multi-user acceptance runs created 48 independently authenticated
controlled identities, 30 live Personal Agent turns, 15 dual-approved Matches,
15 Shared Rooms, and 15 persistent open supply Posts across five intent types.
Every exercised cross-user Task read returned HTTP 403. Final recorded gates
passed 98 Python tests, five frontend tests, lint, type checking, production
build, production concurrency, direct A2A, Pub/Sub, and log audits. See
[docs/V1_LIVE_ACCEPTANCE_REPORT.md](docs/V1_LIVE_ACCEPTANCE_REPORT.md).

These are controlled test accounts, not organic users or marketplace-scale
claims. No finite test suite proves the absence of all defects.

## Prior-Work Disclosure

The PairPilot concept was explored before the hackathon, but no earlier source
code was reused. The Google ADK runtime, A2A integration, Firestore platform,
Cloud deployment, UI, and tests were built from scratch during the hackathon.
See [PRIOR_WORK.md](PRIOR_WORK.md).

## Known Limitations

- The validation cohort is controlled; PairPilot does not claim organic users
  or production marketplace scale.
- Email/password authentication verifies control of an email account; it is not
  government-ID or real-world identity verification.
- FCM browser push is not shipped. Updates use authenticated in-app
  notifications, Pub/Sub processing, and periodic reconciliation.
- Five canonical intent types are accepted, but room-share has the deepest
  specialized policy; the others share a generic policy layer.
- Candidate exchanges are bounded and normally resolve in one substantive
  round even though a six-round ceiling exists.
- Password-reset delivery, long network-disruption soak, and a dedicated live
  material-change race were not part of the final acceptance matrix.
- PairPilot does not book, pay, guarantee safety or compatibility, or let an
  Agent make the final commitment.
