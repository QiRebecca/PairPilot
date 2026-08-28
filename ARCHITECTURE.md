# Architecture

PairPilot separates model autonomy from infrastructure authority. Models choose
semantic actions; deterministic services decide whether each action is typed,
visible, current, private, idempotent, and authorized.

## Runtime flow

1. The React network UI opens an SSE request on the public orchestrator Cloud
   Run service.
2. Qi Agent runs through Google ADK against Vertex AI
   `gemini-3.7-flash` at the global endpoint.
3. Model-selected tools read only permitted Firestore documents and write
   observable turns/events.
4. The authenticated A2A client resolves a peer's public Agent Card and invokes
   its private JSON-RPC endpoint using the Cloud Run runtime identity.
5. Alice, Maya, or Lena executes an isolated ADK runner with owner-scoped facts,
   validates a `PeerDecision`, and returns a typed A2A envelope.
6. Qi treats claims as reports. Deterministic availability and cost services
   build a versioned proposal.
7. After both agents accept, infrastructure places a hold and exposes the
   effect contract. The scheduler stops.
8. A human approval triggers commit-time revalidation and one preconditioned
   Firestore commit. Relationship/memory growth is a consequence of the
   committed event, not a predicted model outcome.

## Trust boundaries

- **Browser:** public and untrusted; receives no private profiles or cloud
  credentials.
- **Public orchestrator:** rate-limited; one run at a time; validates all user
  and model actions.
- **Private peer service:** Cloud Run Invoker permission only for the runtime
  service account.
- **Vertex AI:** live model calls through service identity; no API key.
- **Firestore:** current authority and idempotency source of truth.
- **Pub/Sub:** at-least-once observable events backed by a durable Firestore
  outbox.

## Data distinctions

Current facts (`availability`, `holds`, `approvals`, proposal versions) are
never inferred from memory. Peer reports live in `beliefs` with
`REPORTED_CLAIM`. Relationships and memories require provenance. Messages and
agent turns are observable but never hidden chain-of-thought.

The rendered overview is [docs/architecture.png](docs/architecture.png); its
source is [docs/architecture.mmd](docs/architecture.mmd).
