# Devpost submission — final copy

## Project title

**PairPilot — A Marketplace Where Personal Agents Find the Right People**

## Tagline

Tell your Personal Agent what you need. It publishes the request, monitors the
market, negotiates with other Agents, and brings both humans back only for the
final decision.

## Track

**Taskmaster**

## Inspiration

Finding the right person for a real-world plan is rarely solved by a search
result. A conference roommate, event companion, coffee chat, meal companion,
or hackathon teammate has changing availability, personal compatibility, and
privacy boundaries. The user still has to write the post, watch several
channels, repeat questions, compare uncertain answers, and determine whether a
possible agreement is current.

We wanted to give each person a persistent Agent that can operate that workflow
without turning private context into a public profile and without giving a
model the power to commit on the person's behalf.

## What it does

PairPilot is an agent-operated marketplace for real-world plans. Every
registered user has one persistent Personal Agent and one integrated
conversation. The user describes an outcome in ordinary language; the Agent
clarifies only what is necessary, creates a private Task, and drafts a
privacy-aware public Post. The user can revise, cancel, or publish the draft,
or delegate publication within a configured authority mode.

Once a Post is open, PairPilot continues working while the user is away. It
monitors compatible Posts in shared Communities, opens separate Agent Rooms,
and lets several independently owned Personal Agents exchange
minimum-necessary information. Candidate assessments distinguish verified
facts, peer reports, negotiated terms, conflicts, and uncertainty. Rankings
change when evidence or availability changes, and a late candidate can be
evaluated without the requester reopening the browser.

When a proposal is ready, PairPilot brings both people back. Both Personal
Agents must first accept the same versioned, reversible proposal. Each human
then sees an owner-perspective effect contract and approves independently. The
first approval waits. Only the second approval of the same current version can
atomically create the Match and unlock the Shared Room. The completed result
can update a provenance-backed Network relationship and propose private Memory
that remains inert until its owner confirms it.

## How we built it

The authenticated product is a React and TypeScript application backed by a
FastAPI orchestrator on Cloud Run. Firebase Authentication provides separate
identities. Every Firebase UID maps to a distinct Personal Agent, canonical
conversation, owner-only Tasks, policies, ADK sessions, and Memory.

Google ADK runs `gemini-3.7-flash` through Vertex AI. The model selects bounded
typed tools for clarification, Task and Post work, candidate inspection,
communication, and presentation. Successful messages persist model, session,
invocation, tool, token, latency, and UI-card provenance. There is no canned
assistant fallback: a failed model turn is reported and no fabricated answer is
saved.

Firestore Native is the source of truth for private and public projections,
Post lifecycle, A2A provenance, candidate rankings, proposals, holds,
approvals, Matches, Rooms, relationships, and Memory. Publishing first stores a
durable outbox event. Pub/Sub invokes an OIDC-authenticated Cloud Run worker,
and Cloud Scheduler provides bounded reconciliation. Leases, idempotency,
quotas, proposal versions, update-time preconditions, and an atomic commit keep
model autonomy inside explicit authority boundaries.

Agent-to-Agent communication uses A2A Agent Cards and JSON-RPC. Every envelope
is bound to the acting Agent, source and target Intent Posts, Task, pair
session, and provenance. The receiving Agent sees only reviewed public fields
and its owner's allowlisted policy—not the other person's private conversation.

## Google technologies used

- Vertex AI global endpoint with live **`gemini-3.7-flash`**
- Google Agent Development Kit **2.8.0**
- Cloud Run for the public orchestrator/UI and authenticated peer-Agent service
- Firestore Native in `europe-west2` for authoritative state and provenance
- Pub/Sub for durable event-driven background work
- Cloud Scheduler for five-minute recovery and reevaluation
- Firebase Authentication for independent email/password identities
- IAM and Google-signed OIDC tokens for service-to-service authorization
- Cloud Logging for runtime, invocation, and deployment evidence
- Cloud Build and Artifact Registry for immutable containers

We also use A2A Python SDK 1.1.2 and JSON-RPC 1.0 for interoperable Agent
transport.

## Other data sources

PairPilot uses no purchased, scraped, or third-party people dataset. Marketplace
content comes from user-reviewed Posts and clearly labelled controlled test
accounts. Current state, availability, candidate evidence, and relationship
history are stored in PairPilot's Firestore database. Peer-Agent statements are
treated as unverified reports unless confirmed by authoritative platform state
or later human outcome feedback.

## Challenges

The hardest problem was separating semantic agency from authority. Gemini
should decide what to clarify, whom to contact, what to ask, and how evidence
changes a recommendation—but a peer message must never grant permission,
publish protected data, reserve stale capacity, or approve a Match.

We also had to make background work reliable under retries and concurrency.
Posts can arrive while users are offline; Pub/Sub can redeliver; model calls can
fail or return invalid structure; two people can act on the same proposal at
nearly the same time. PairPilot therefore uses durable events, pair-scoped
sessions, leases, idempotency keys, bounded retries, exact proposal versions,
and a preconditioned atomic commit.

Finally, we had to make real multi-user privacy observable. The browser has no
direct Firestore access. Every protected request derives ownership from a
fresh Firebase token, and our live acceptance deliberately attempted
cross-user Task reads and expected HTTP 403.

## Accomplishments

- One persistent live Gemini/ADK conversation that creates and manages real
  Tasks and reviewable Posts.
- Event-driven discovery and reevaluation that continue without an open browser.
- Multiple independently authenticated users and independently owned Personal
  Agents, with separate human-Agent and A2A sessions.
- Up to five contacted candidates, bounded parallel negotiation, evidence
  separation, rank-change provenance, primary and backup candidates.
- Two Agent acceptances, two independent human approvals, and one atomic Match.
- Participant-scoped Agent Rooms and Shared Rooms, optional match-scoped contact
  cards, outcome feedback, Network provenance, and confirmed-only Memory.
- Fail-closed privacy guards, deny-all browser Firestore rules, report/block
  propagation, and verified cross-user authorization.
- Three final acceptance runs using 48 independently authenticated controlled
  identities, 30 live Personal Agent turns, 15 dual-approved Matches, and 15
  Shared Rooms across five intent types.
- Final recorded gates of 98 Python tests, five frontend tests, lint, strict
  type checking, production build, direct A2A, Pub/Sub, concurrency, and Cloud
  Logging audits.

These were **controlled test accounts**, not organic users or a claim of
marketplace scale.

## What we learned

Agent-native products need two complementary systems. The semantic system
should be flexible: persistent context, typed tools, multi-Agent dialogue, and
evidence-aware judgment. The authority system should be deliberately boring:
authenticated ownership, minimal disclosure, explicit lifecycle, versioned
consent, idempotency, and atomic state transitions.

We also learned that provenance is part of the interface, not just an audit
log. A useful answer is stronger when the user can see that it came from a
fresh model invocation, which tools ran, why a candidate moved, what remains
uncertain, and exactly what an approval will change.

## What is next

After judging, we would run a small opt-in beta, deepen task-specific policy
beyond the current five canonical intent types, add longer reliability and
material-change race testing, improve moderator tooling, and evaluate optional
browser push notifications. We would not add booking or payment until identity,
safety, dispute, and regulatory boundaries are designed for that higher-risk
authority.

## Testing instructions

Open <https://pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app/> and use the
prepared email-verified controlled account supplied privately to judges. Start
in **My Agent**, send a natural-language request, and expand **Response audit**
under an Agent message to inspect the fresh model, invocation, latency, token,
and tool provenance. Review or publish the Agent-drafted Post, open it in
**Explore**, and inspect **Rooms** and the ranked candidate pool.

For the fastest full-path review, sign into the pre-populated requester. It
already contains several candidate assessments, at least two Agent Rooms, a
completed Match, Network evidence, and a proposed or confirmed Memory. To test
dual approval, approve the prepared current proposal as the requester, then use
the separate candidate credential supplied privately and approve the identical
version. Confirm that the first approval waits and the second creates one Match
and unlocks the Shared Room.

No judge email verification, team inbox, Firebase or Google Cloud access, or
global database reset is required. Allow roughly 10–90 seconds for a live
Gemini turn and 3–5 minutes for the recommended prepared workflow. See the
credential-free [judge testing guide](docs/JUDGE_TESTING_GUIDE.md).

## Prior-work disclosure

The PairPilot concept was explored before the hackathon. No earlier source code
was reused. This repository began empty during the hackathon; the Google ADK
runtime, A2A integration, Firestore coordination and authority layer, Pub/Sub
workflow, Cloud Run deployment, frontend, tests, and submitted product were
implemented from scratch during the event. Full disclosure:
[PRIOR_WORK.md](PRIOR_WORK.md).

## Scope and limitations

PairPilot does not claim organic users, marketplace scale, government-ID
verification, guaranteed compatibility, hotel booking, payment processing, or
fully autonomous final commitment. FCM browser push is not part of this
release. The shipped update channels are authenticated in-app notifications,
Pub/Sub background work, and periodic reconciliation.
