# Product gap audit: intent marketplace correction

Audit date: 2026-08-29. Baseline commit: `9930444`. Baseline tag:
`pre-intent-marketplace-9930444`.

## Baseline verification

- Clean worktree on `main` at `9930444`.
- Ruff, ESLint, strict mypy across 37 source files, TypeScript checking,
  34 Python unit tests, one React test, and the Vite production build passed.
- The existing public deployment passed its bounded retry verification. It was
  still running `pairpilot-orchestrator-00005-lbc` and
  `pairpilot-peer-agents-00009-8l4`, with zero committed matches.
- A protective tag and the branch `intent-marketplace-product-layer` were
  created before product changes.

## Findings

### Where the current goal comes from

`run_golden_path.py` defines a module-level `GOAL_TEXT`. `web.py` returns that
constant from every public state response and starts `run()` without user
input. `GoldenPathRuntime.initialize()` creates an `intents` document using a
new `goal_id`, but that document is a run-scoped goal record rather than a
reviewed marketplace post. The seed script does not seed a Qi workflow goal;
the public run endpoint creates it automatically.

### UI assumptions

`web/src/App.tsx` installs the full goal in `emptyState`, renders a “Current
goal” card, and exposes “Start live run” as the primary action. There is no
composer, draft, field-level provenance, review/edit step, publish action, post
registry, or post lifecycle. Expired approval copy tells the user to reset and
run again.

### Existing `intents` collection

The collection already exists. It is listed among mutable workflow
collections, and `GoldenPathRuntime.initialize()` writes one document keyed by
`goal_id`. Current fields are `goal`, dates, preference, maximum cost, and
commitment boundary. The correction will evolve this collection in place into
public intent posts and add a separate owner-scoped `intent_private` collection
for raw input and protected references.

### Current discovery model

`search_open_agents()` scans `agent_public_cards`, filtering generic people by
conference, gender, and cold-contact status. Maya and Lena are represented as
available profiles; neither owns an active need. Active matching therefore
searches people rather than current posts. Alice is correctly represented as a
relationship owner and introducer.

### Current hold scope and expiry

The typed `Hold` stores `goal_id` and `candidate_agent_id`. Conflict detection
in `CoordinationAuthority.place_hold()` is goal-scoped, not bound to both
source and target intents or target capacity. Firestore hold documents inherit
that shape. The demo creates a ten-minute hold. The previously displayed hold
expired because approval happened outside that finite window; there was no
renewal endpoint, and the UI only offered reset. The correction will use a
15-minute intent-pair hold, a visible countdown, and explicit revalidation.

### A2A scope and duplicate sessions

`A2AMessageEnvelope` binds run, session, sender, recipient, speech act, claims,
and optional proposal. It has no source or target intent identifiers.
Per-candidate counters are keyed only by agent ID, so multiple simultaneous
intents could collide and warm plus open discovery has no persisted canonical
intent-pair session key.

### Positive commit endpoint

`POST /api/demo/approve` requires the exact phrase `APPROVE VERSION N`, creates
a human approval tied to the displayed disclosure hash, then calls
`commit_approved_match()`. That function revalidates proposal expiry, hold,
availability, both agent acceptances, approval version, disclosure hash, and
Firestore update-time preconditions. It atomically writes a match, releases
the selected hold, commits proposal/run/request state, updates Alice, adds a Qi
to candidate relationship, and creates scoped memory. It does not currently
validate or transition source/target intent posts, release other intent-pair
negotiations, consume post capacity, or emit `intent.matched` for both posts.

### Relationship-memory trigger

The production relationship and memory writes originate in
`commit_approved_match()` after the authoritative commit checks. Peers cannot
write this memory. The architecture PNG is misleading, however: its visible
“commit → learn” arrow starts beside the Lena node. The corrected diagram will
make Firestore/Pub/Sub `match.committed` the source.

### Reset gap

Reset deletes the entire `intents` collection and then reseeds identities,
profiles, relationships, and availability. It does not reseed Maya/Lena intent
posts. The corrected reset must delete only mutable Qi/workflow state, then
seed Maya and Lena OPEN posts while leaving Qi with no active request.

## Safe extension points

- `pairpilot_schemas/domain.py`: add intent lifecycle, post, pair-session, and
  intent-scoped hold contracts while preserving existing contracts during the
  migration.
- `pairpilot_schemas/agent_messages.py`: add required intent routing.
- `infra/seed_demo.py`: evolve schema and seed only peer-owned OPEN posts.
- `workflow/golden_path.py`: accept a published source intent, replace active
  matching with open-post search, and preserve model-selected strategy.
- `a2a_client.py` and the peer executor: propagate and validate intent IDs.
- `domain/firestore_commit.py`: extend the existing atomic transaction instead
  of creating a parallel commit path.
- `web.py`: add draft, publish, revalidate, and safe public registry APIs while
  preserving current approval authority.
- `web/src/App.tsx` and `styles.css`: replace dashboard-first navigation with
  composer/review/overview/matched states and retain Network/Audit as secondary
  views.

## Critical correction boundary

The agent engine, independent ADK contexts, authenticated A2A transport,
privacy guard, deterministic cost calculation, effect approval, Firestore
preconditions, Pub/Sub outbox, and provenance pipeline remain. The product
layer must make user-created posts authoritative inputs to that engine; it must
not introduce a deterministic “best candidate” matcher or a scripted outcome.
