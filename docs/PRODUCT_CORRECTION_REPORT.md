# Intent marketplace product correction report

Report date: 2026-08-29. Branch: `intent-marketplace-product-layer`.
Protected baseline: `pre-intent-marketplace-9930444`.

## Outcome implemented locally

The original Gemini/ADK/A2A/Firestore/Pub/Sub coordination engine remains. The
product entry point is now an empty intent composer instead of a pre-seeded
goal. A live Qi drafting agent creates a reviewable, privacy-tiered post; user
publication creates an authoritative `OPEN` marketplace intent. Discovery,
A2A, proposals, holds, approval, and commit are all bound to source and target
intent IDs.

The main UI is request-centered and exposes five views: Overview, Agent Work,
Network, Audit, and Memory. Network and technical logs remain transparency
surfaces rather than the product's opening screen.

## Data migration

The existing `intents` collection was evolved in place. New owner-private data
uses `intent_private`; negotiation identity uses `intent_pair_sessions`.
Reset explicitly deletes mutable workflow collections and reseeds only Maya and
Lena `OPEN` posts, their owner-private contexts, identities, availability, and
the Alice relationship graph. It never seeds a Qi goal, successful run, match,
or memory.

## Authority changes

- Proposal versions are scoped to one intent pair.
- A2A messages require source intent, target intent, and canonical pair ID.
- Holds reserve intent capacity for 15 minutes rather than locking a person.
- Safe failures/no-match release only the current run's uncommitted capacity.
- Explicit revalidation can renew an expired hold only while the proposal,
  posts, capacity, and both acceptances remain current.
- Atomic commit validates both post documents and the pair session, closes both
  posts, and releases other negotiations in the same transaction.
- Relationship/memory writes remain downstream of the committed match.

## Authenticity evidence

The production code contains no seeded Qi goal, fixed Maya selection, fixed
contact order, replayed UI events, or draft fallback. The live draft adapter
uses the exact configured Vertex model and rejects schema-invalid output.
Automated variants prove that `$70` permits the `$62` compromise while `$50`
does not.

A fresh no-write live Vertex draft on 2026-08-29 extracted `$50` as
`explicit_user_input`, preserved partial overlap, inferred `2026-07-06` through
`2026-07-10`, marked the year as `agent_inference`, and surfaced that inference
in `uncertainties`. This verifies the corrected prompt without writing demo
state.

## Local verification

- Ruff: passed.
- ESLint: passed with zero warnings.
- Strict mypy: passed across 40 source files.
- TypeScript: passed.
- Python unit tests: 48 passed.
- React tests: passed.
- Vite production build: passed.
- `git diff --check`: passed.
- npm production audit: zero vulnerabilities.
- Python dependency audit after installing the pinned `cryptography 50.0.0`:
  zero known vulnerabilities and no broken requirements.

The earlier three deployed evaluation runs remain historical baseline evidence
for the coordination engine only. They are not represented as tests of this
new composer/publish lifecycle.

## Deployed outcome

The tagged revision passed three fresh composer-to-approval runs and one real
human-approved positive commit. Production traffic now routes 100% to the
verified corrected revisions, while the old revisions remain available for
rollback. See `docs/INTENT_LAYER_DEPLOYMENT_REPORT.md`,
`docs/INTENT_LAYER_EVAL_REPORT.md`, and
`docs/POSITIVE_COMMIT_VERIFICATION.md`.
