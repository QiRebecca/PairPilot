# Devpost submission copy

## Project title

PairPilot — The Relationship Layer for Personal Agents

## Tagline

Humans express intent. Personal agents build relationships and do the
coordination. Infrastructure enforces truth, privacy, and authority.

## Track

Taskmaster

## Inspiration

Finding a conference roommate looks like a recommendation problem, but the
hard part begins after search: private preferences, trust, introductions,
repeated questions, date negotiation, changing state, and knowing when a human
must decide. We wanted personal agents to handle that social work without
turning the human's private life or authority over to a model.

## What it does

Qi enters one goal: find a female roommate for ICML in Seoul, prioritize a
quiet overnight environment, accept partial overlap only below `$70` extra.
Qi's persistent personal agent inspects its relationship with Alice Agent,
discovers open personal agents, sends authenticated A2A messages, evaluates
reported compatibility, calculates cost, negotiates a versioned plan, and
places a temporary hold. It then stops and shows the exact effect contract.
Only Qi can authorize the commitment.

If approved, infrastructure revalidates the proposal, hold, availability, both
agent acceptances, disclosure scope, and idempotency in one atomic Firestore
commit. That committed event—not a model prediction—grows the relationship
network and scoped memory.

## How we built it

The public React/TypeScript interface is a three-panel relationship network,
not a chatbot. It streams real state from a FastAPI orchestrator on Cloud Run.
Qi, Alice, Maya, and Lena are separate Google ADK definitions running live
`gemini-3.7-flash` through Vertex AI. The orchestrator resolves independent A2A
1.0 Agent Cards and calls the private peer service with a Google-signed Cloud
Run identity token.

Firestore Native stores facts, messages, beliefs, proposals, holds, approvals,
matches, relationships, provenance, and a durable Pub/Sub outbox. Typed Python
schemas, deterministic privacy/authority services, and preconditioned Firestore
writes keep model autonomy inside explicit boundaries.

## Google technologies used

- Vertex AI global endpoint: `gemini-3.7-flash`
- Google Agent Development Kit 2.8.0
- Cloud Run: public orchestrator/UI and authenticated peer agents
- Firestore Native: current truth, provenance, relationship memory, outbox
- Pub/Sub: observable domain-event delivery
- Cloud Build and Artifact Registry: immutable containers
- IAM and Cloud Logging: service identity and deployment/run evidence

We also use A2A Python SDK 1.1.2 with JSON-RPC protocol 1.0.

## Challenges

The hardest problem was preserving authentic agent autonomy while guaranteeing
privacy and commitment safety. A semantic script would demo well but would not
be an agent. Unbounded conversation would be authentic but unreliable. We
instead exposed typed capabilities, let Gemini choose the path, and moved
truth/authority into infrastructure.

Live systems also surfaced honest engineering failures: Vertex throttling,
occasional empty model output, an unsupported thinking level, and a serial peer
path that crossed the 90-second bound. Bounded retry, supported model settings,
and a model-selected two-candidate batch brought deployed runs to 38–68 seconds
to the approval boundary without introducing a scripted fallback.

## Accomplishments

- Four independent personal-agent contexts with genuine live model-selected
  tools.
- Authenticated official A2A cards and JSON-RPC exchanges on private Cloud Run.
- A complete deployed workflow from one goal to a versioned, agent-accepted
  proposal and human approval boundary.
- Zero private-memory leakage and zero unauthorized commitment across three
  fresh public runs.
- Distinct valid action trajectories and different generated communication.
- Atomic commit design with 13 preconditioned writes and provenance-backed
  relationship/memory growth.
- A public judge-ready relationship-network UI with reset, live run, pause,
  approval, audit, and memory inspection controls.

## What we learned

Agentic products need two architectures at once: a probabilistic social layer
that can adapt, and a deterministic authority layer that refuses stale or
unauthorized effects. Relationships are also not just embeddings; they need
context, counters, provenance, privacy scope, and event-driven updates.

Most importantly, an approval button is not enough. A human must approve the
current effect—including cost, dates, uncertainty, disclosure, version, and
expiry—not an abstract agent recommendation.

## What's next

With the core safe workflow proven, the next steps are reusable goal schemas,
more relationship contexts, user-editable memories, a durable A2A task store,
and carefully evaluated managed semantic recall. Real payments, booking, and
public onboarding remain intentionally out of scope until identity, dispute,
and stronger abuse controls exist.

## Testing instructions

1. Open the public URL; no sign-in is required.
2. Click **Reset demo**.
3. Click **Start live run** and watch live edges, messages, turns, model badge,
   and run ID. A typical run takes 40–75 seconds.
4. Inspect the audit log and relationship memory drawer.
5. At the approval boundary, inspect the full effect contract. Approval is a
   real internal demo commit; if you do not want to commit it, use Reject or
   Reset.
6. Refresh the page to confirm Firestore persistence.

Synthetic facts only. No real booking or payment is performed.
