# Architecture

PairPilot is an agent-operated intent marketplace. Current needs live as
capacity-bearing intent posts; durable relationships help personal agents
decide whom to contact. Models choose semantic strategy, while deterministic
services decide whether every read, disclosure, hold, approval, and commit is
current and authorized.

![PairPilot architecture](docs/architecture.png)

## Product-to-runtime flow

1. The user describes a need in the PairPilot User App.
2. Qi Agent runs a live structured-output Google ADK turn with Vertex AI and
   drafts public, agent-only, protected, and field-provenance sections.
3. Nothing is discoverable until the user reviews, edits, and publishes. The
   published document becomes an `OPEN` post in the Intent Registry; its raw
   request and protected references remain in owner-scoped `intent_private`.
4. Qi Agent searches current `OPEN` posts and may also inspect relationship
   memory to request a warm introduction. It never searches private profiles.
5. Qi, Alice, Maya, and Lena communicate through authenticated A2A envelopes
   bound to source intent, target intent, and a canonical intent-pair session.
6. Gemini chooses the strategy and tool sequence. Deterministic services own
   availability, cost math, proposal versions, privacy checks, capacity, and
   authority.
7. After both agents accept one current version, infrastructure reserves one
   unit of intent capacity for 15 minutes and shows the human the exact effect.
8. Human approval triggers update-time revalidation and one Firestore atomic
   commit: create the match, consume and close both posts, release conflicting
   sessions/holds, update provenance, and persist durable outbox events.
9. Only `match.committed` / `intent.matched` events can produce relationship
   growth and scoped editable memory. No peer agent can write success memory.

## First-class stores

- `intents`: public marketplace documents with lifecycle, owner, capacity,
  expiry, public constraints, negotiation boundaries, and provenance.
- `intent_private`: owner-only raw input, agent-only constraints, protected
  references, and explicit read scope. It is never part of public API state.
- `intent_pair_sessions`: one canonical negotiation session per post pair.
- `agent_messages`: intent-scoped A2A requests and responses; claims remain
  `REPORTED_CLAIM` rather than authoritative facts.
- `proposals`, `proposal_acceptances`, `holds`, `approval_requests`,
  `approvals`, and `matches`: the authority pipeline.
- `relationships`, `relationship_events`, and `memories`: downstream learning
  with match/event provenance.
- `events`: durable Firestore outbox delivered through Pub/Sub.

## Trust boundaries

- **PairPilot User App:** public and untrusted; receives whitelisted public
  posts plus only the signed-in demo owner's review data.
- **Public Cloud Run orchestrator:** rate-limited, one run at a time, validates
  user/model actions, and streams observable state—not hidden chain-of-thought.
- **Private Cloud Run peers:** callable only by the runtime service identity;
  each peer has isolated owner context and its own A2A Agent Card.
- **Vertex AI:** live `gemini-3.7-flash` calls through service identity; there is
  no API key, replay path, or silent model fallback.
- **Firestore:** source of current truth, idempotency, capacity, and commit
  preconditions.
- **Pub/Sub:** at-least-once event delivery backed by the durable outbox.

The diagram source is [docs/architecture.mmd](docs/architecture.mmd), rendered
by `python3 infra/render_architecture.py`.
