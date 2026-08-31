# PairPilot Architecture

PairPilot is an agent-operated marketplace for real-world plans. Each
authenticated user owns one persistent Personal Agent. The user stays in one
conversation while the Agent turns ordinary language into a privacy-aware
Post, monitors the live market, talks with several other Personal Agents,
ranks candidates as evidence changes, and asks both humans to approve before
the system creates a Match.

![PairPilot final architecture](docs/architecture.png)

## Main flow

1. **Conversation.** Firebase Authentication identifies User A or User B. A
   verified Firebase ID token reaches the authenticated Cloud Run API; the
   browser is never trusted to declare an owner or participant identity.
2. **Agent-drafted Post.** The owner's persistent Personal Agent uses its
   global ADK session for continuous conversation and task-scoped ADK sessions
   for bounded work. A live Vertex AI `gemini-3.7-flash` turn drafts the public
   projection while raw goals, boundaries, and private instructions remain in
   owner-scoped Firestore records.
3. **Publish.** The reviewed projection enters the Intent Post Registry. Under
   copilot policy the human approves it; under explicitly selected Agent
   autonomy the Agent may publish it. Publishing never authorizes a final
   commitment.
4. **Background market monitoring.** A durable `intent.published.v2` event is
   delivered by Pub/Sub to the OIDC-protected Cloud Run worker. The worker
   maintains the Multi-Candidate Pool and continues to reconcile new or changed
   compatible Posts with bounded, idempotent retries.
5. **Multiple A2A negotiations.** PairPilot opens intent-pair Coordination
   Rooms. Each Personal Agent receives only the other Post's approved public
   projection plus its own owner's allowlisted policy. Separate task-scoped
   Gemini turns generate real A2A messages with source, target, task, intent,
   session, and model provenance.
6. **Dynamic ranking.** Candidate assessments are recomputed from compatibility
   and new negotiation evidence. The owner sees a ranked list rather than a
   single preselected answer.
7. **Proposal, hold, and dual approval.** The selected proposal reserves both
   Posts with a versioned hold. Agent acceptance is reversible and cannot
   commit either human. User A and User B independently approve the same current
   proposal and effect hashes.
8. **Atomic Match.** One Firestore transaction validates both approvals and
   current capacity, creates exactly one Match, and consumes or updates the two
   Posts without a one-sided success state.
9. **Room, Network, and Memory.** A successful Match promotes the Agent Room to
   a participant-only Shared Room, adds owner-scoped Relationship Network
   entries, and proposes scoped Memory. Memory becomes durable only after its
   owner confirms it.

## Runtime and Google Cloud components

- **Firebase Authentication** provides independently authenticated identities,
  session restoration, and fresh ID tokens for protected calls.
- **Cloud Run** hosts the web API, persistent Personal Agent runtime, A2A
  orchestration, and background worker. Server middleware derives the UID and
  enforces owner, participant, or administrator authorization on every protected
  resource.
- **Vertex AI `gemini-3.7-flash`** powers live Personal Agent drafting,
  clarification, negotiation, and candidate-assessment turns. Deterministic
  application services—not model text—decide publication, disclosure, holds,
  approvals, and commits.
- **Firestore** is the authoritative store for users, Personal Agents, global
  and task-scoped ADK sessions, conversations, tasks, private intents, public
  Posts, candidate assessments, Coordination Rooms, proposals, holds, human
  approvals, Matches, Shared Rooms, relationships, confirmed memories, leases,
  and the durable event outbox. Direct browser access is denied.
- **Pub/Sub** wakes background monitoring from durable publish events through an
  audience-bound Google OIDC push identity. Delivery is retryable; workers use
  leases and idempotency keys so duplicate events do not duplicate outcomes.
- **Cloud Logging** records trace IDs, authenticated principals, Agent/model
  provenance, event delivery, worker outcomes, and failures without making
  private instructions public.

## Persistent Agent and session model

Every user has a stable `personal_agent_id`. The global ADK session preserves
one continuous user-facing conversation across tasks and navigation. Each task
also has an isolated ADK session for its Post draft, market monitoring,
candidate evidence, and A2A work. A task-scoped tool can update only resources
owned by that task; returning to the global conversation does not discard task
state.

The Cloud Run runtime is generic: it loads the authenticated owner's Agent,
privacy policy, autonomy mode, permitted memory, and requested task scope. It
does not rely on fixed demo identities or hardcoded Agent replies.

## Authority and privacy boundaries

- Only reviewed public fields enter the Intent Post Registry or another
  Agent's context. Raw conversation, private instructions, unconfirmed memory,
  contact details, and owner UID remain private.
- Public discovery never implies permission to reveal identity or contact
  information. A2A coordination happens inside participant-scoped Agent Rooms.
- Agent acceptance and human approval are separate records. Neither Agent can
  create a Match, and one human approval is insufficient.
- The atomic commit rechecks proposal version, effect hashes, capacity, holds,
  blocks, and both approvals. Stale or repeated requests fail closed or return
  the already committed result.
- Relationship records and memories are owner-scoped. A proposed memory is not
  treated as confirmed until its owner explicitly accepts it.

## Authoritative collections

- Identity and policy: `users`, `personal_agents`, `user_privacy_configs`,
  `user_autonomy_configs`, `usage_quotas`.
- Conversation and task state: `conversations`, `conversation_messages`,
  `task_workspaces`, `intent_private_data`, ADK session records.
- Marketplace and monitoring: `intent_posts`, candidate assessments,
  `intent_pair_sessions`, `execution_leases`, `events`.
- Coordination and commitment: `coordination_rooms`, `room_participants`,
  `room_messages`, `proposals`, `proposal_acceptances`, `holds`,
  `human_approvals`, `decisions`, `matches`.
- Post-match state: shared-room records, `relationships`, `memories`, `blocks`,
  and `reports`.

The diagram source is [docs/architecture.mmd](docs/architecture.mmd). The PNG is
reproducibly generated with `python3 infra/render_architecture.py`.
