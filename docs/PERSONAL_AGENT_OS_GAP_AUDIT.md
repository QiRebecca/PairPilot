# Personal Agent OS gap audit

Baseline: commit `665af083eae128eab28aa19c84622e996bfd7c8c` on
`intent-marketplace-product-layer`, protected by
`pre-personal-agent-os-665af08`. Production at audit time routed 100% to
orchestrator `pairpilot-orchestrator-00011-xeg` and peer service
`pairpilot-peer-agents-00013-yem`.

## Baseline verification

- Ruff, ESLint, strict mypy across 40 Python source files, TypeScript, 48
  Python unit tests, three React tests, Vite production build, diff and secret
  scan: passed.
- Anonymous production health, state projection, OG asset and both Cloud Run
  traffic routes: passed.
- Exact runtime remained `LIVE GEMINI + GOOGLE ADK + A2A` on
  `gemini-3.7-flash`.

## Current product structure

| Area | Current implementation | Personal Agent OS gap |
|---|---|---|
| Routing | One React render tree; tabs are component state | No direct links, history, application routes or persistent shell |
| Frontend ownership | `web/src/App.tsx` owns API types, fetching, SSE, composer, review, overview, graph, audit, memory and approval | Monolithic 542-line component prevents page- and task-level isolation |
| Default surface | Composer when empty; matched result when the shared run is committed | No persistent global Qi conversation or task registry |
| Task model | Qi intent, run and intent-pair session imply one workflow | No first-class `TaskWorkspace`, task conversation or cross-task index |
| Conversations | A2A messages are scoped to an intent pair and run | No user↔Qi global/task messages, channel visibility or room model |
| Intents | Public `intents` plus owner-only `intent_private` | Strong base to retain; task ownership and authorship need formal links |
| Discovery | `search_open_intents` returns redacted active posts | Suitable for Explore; only Maya/Lena are seeded |
| Candidate logic | Evidence beliefs and dispositions are stored per run | No materialized, task-scoped `CandidateAssessment` projection |
| Coordination | Canonical `intent_pair_sessions` and intent-scoped A2A envelopes | No product-level room, participant, mode, channel or authorship objects |
| Decisions | `approval_requests` and expired-hold recovery | No shared Decision Inbox projection for draft review, approval and memory |
| Presentation | Frontend decides which component follows current state | No allowlisted, permission-checked Presentation Directive protocol |
| Relationships | Provenance-backed relationship documents and graph | Graph is product-capable but has no filter/detail surface |
| Memory | Scoped committed-outcome memories | No confirmation/correction/archive/use-for-matching controls |
| Reset | Deletes an explicit workflow allowlist and reseeds world facts | Must include new mutable OS collections and keep infrastructure/quota facts |
| API | `web.py` provides one demo state projection and intent/run actions | Needs OS bootstrap, task, conversation, room, feed, decision and directive APIs |

## Existing collections

The current workflow uses `runs`, `intents`, `intent_private`,
`intent_pair_sessions`, `agent_turns`, `agent_messages`, `beliefs`, `proposals`,
`proposal_versions`, `proposal_acceptances`, `holds`, `approval_requests`,
`approvals`, `matches`, `events`, `memories`, `relationships` and
`relationship_events`. Seeded world facts include `users`, `agents`, public
agent cards, owner-private profiles, availability and seed metadata.

There are no existing collections named `task_workspaces`, `conversations`,
`conversation_messages`, `candidate_assessments`, `coordination_rooms`,
`room_participants`, `room_messages`, `presentation_directives`,
`decision_inbox` or `internal_worker_runs`; adding those names does not create
conflicting duplicate concepts. Existing `intents`, `matches`, `relationships`
and `memories` will be reused rather than renamed.

## Preserve without semantic weakening

- Qi, Alice, Maya and Lena remain persistent Personal Agent identities.
- Live Gemini continues to select coordination strategy and tools.
- Authenticated A2A messages retain source/target intent and canonical pair
  session identity.
- Public, agent-only and protected data remain separate.
- Peer claims remain reported claims.
- Proposal version, deterministic cost, post-scoped hold, exact approval and
  atomic Firestore commitment remain the only authority path.
- Relationship and scoped memory continue to derive from committed events.
- Audit evidence remains available, but moves behind a product route.

## Safe extension seams

1. Add strict shared schemas for tasks, conversations, decisions, rooms,
   assessments and presentation directives in `pairpilot_schemas`.
2. Add an OS projection/service beside the existing golden-path runtime; do
   not rewrite the authority transaction.
3. Materialize task/room/decision projections when drafts, runs, proposals and
   commits change.
4. Treat an existing intent-pair session as the authoritative negotiation-room
   anchor.
5. Split the React application into a routed shell, shared state provider and
   page components while reusing the current review, approval, graph and audit
   behavior.

## Authenticity limits

The initial OS refactor will not claim dynamic internal workers unless real
bounded worker runs are added and persisted. It will label Maya and Lena as
synthetic demo participants, keep agents-only transcripts read-only, and avoid
claiming real human-to-human messaging. The approved ICML flow remains the only
live negotiation scenario; additional Explore posts are browseable synthetic
world state only.
