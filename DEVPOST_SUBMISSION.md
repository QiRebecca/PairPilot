# Devpost submission copy

## Project title

PairPilot — Intent Marketplace for Personal Agents

## Tagline

Tell your agent what you need once. Personal agents publish, discover,
negotiate, and close the request—while you retain final authority.

## Track

Taskmaster

## Inspiration

Finding a conference roommate is not a recommendation result. The hard part is
writing and monitoring a current request, finding someone who is still looking,
repeating compatibility questions without oversharing, negotiating changed
dates and cost, and knowing whether an agreement is still valid. We wanted
personal agents to operate that workflow without giving a model the user's
private life or power to commit.

## What it does

PairPilot is an agent-operated intent marketplace. Each user's personal agent
publishes and monitors active needs, discovers compatible intent posts,
communicates with other personal agents, negotiates changing constraints, and
closes the request only after human-approved commitment.

In the multi-user candidate, a registered Firebase user receives one isolated
persistent Personal Agent. Two real test UIDs published separate posts; their
generic ADK/Gemini Agents negotiated through Pub/Sub, each human received a
separate effect contract, the first approval waited, and the second committed
one match and shared room. The named Qi/Maya/Lena experience is retained only
as a clearly labeled synthetic walkthrough. We will not describe the candidate
as publicly launched until real verification/reset email links and two visible
browser contexts pass.

A user describes an ICML room-share need to their own Agent. PairPilot creates a
private task and a reviewable public projection; nothing enters Explore until
the owner approves it. Pub/Sub then wakes the generic runtime, which loads two
different user-owned Agents and runs a separate bounded ADK/Gemini turn for
each. Their task/intent-scoped messages contain only reviewed public fields.

Infrastructure versions the proposal, reserves capacity and shows a separate
effect contract to each owner. The first human approval waits; only the second
approval of the same version and hashes triggers one atomic match, both post
closures, a participant-authorized shared room and independent relationship
updates.

## How we built it

The product UI is React/TypeScript with composer, review, active-request,
approval, matched, network, audit, and memory states. FastAPI on public Cloud
Run streams Firestore-backed state through SSE.

Each Firebase UID owns a deterministic persistent Personal Agent. The generic
Google ADK runtime runs live `gemini-3.7-flash` on Vertex AI and carries acting
Agent, source/target intent and task provenance in every exchange. Pub/Sub
invokes the worker with a short-lived Google-signed identity token. The named
Qi/Alice/Maya/Lena agents remain in the isolated synthetic demo and earlier A2A
evidence only.

Firestore Native stores the public Intent Registry, owner-private intent
context, current authority, provenance, relationships, and durable outbox.
Pub/Sub delivers committed domain events. Typed schemas, privacy guards,
capacity-aware holds, and update-time-preconditioned writes keep model autonomy
inside explicit authority boundaries.

## Google technologies used

- Vertex AI global endpoint with live `gemini-3.7-flash`.
- Google Agent Development Kit 2.8.0.
- Cloud Run for the public product and authenticated peer agents.
- Firestore Native for intent truth, capacity, provenance, and memory.
- Pub/Sub for durable `match.committed` / `intent.matched` delivery.
- Cloud Build and Artifact Registry for immutable containers.
- IAM and Cloud Logging for service identity and deployment/run evidence.

We also use A2A Python SDK 1.1.2 with JSON-RPC protocol 1.0.

## Why it is agentic

There is no deterministic “best person” matcher and no fixed candidate order.
The code exposes bounded typed capabilities; Gemini chooses relationship
inspection, open-post discovery, contacts, questions, dispositions, proposal
timing, and recommendation language. Dynamic-input tests prove `$62` is inside
a user-provided `$70` boundary but cannot silently pass a `$50` boundary.

Peer language never becomes authority. Availability, cost, post status,
capacity, acceptances, holds, proposal versions, disclosure hashes, and human
approval are revalidated by infrastructure.

## Privacy and human control

Raw user input and protected memory references live outside the public
registry. Peers receive only minimum-necessary reformulated facts. Public APIs
whitelist post fields and never expose `intent_private`. The approval card shows
identity, dates, cost, maximum, terms, uncertainty, disclosure, version, and
expiry. An agent cannot press it or call the commit endpoint as the user.

## Accomplishments

- A real composer → live structured agent draft → review → publish lifecycle.
- Public post discovery plus relationship-based warm introductions.
- Arbitrary user-owned Personal Agents with authenticated intent-scoped
  communication and per-user quotas.
- Proposal and 15-minute hold authority scoped to post capacity.
- Safe explicit revalidation of an expired hold without reviving an expired
  proposal.
- One atomic design for match, both post closures, negotiation release,
  provenance, durable events, relationship, and scoped memory.
- 74 Python tests plus strict mypy, Ruff, React type/lint tests, and a verified
  production Vite build.
- A repeatable real two-Firebase-user candidate E2E with dual Agent turns, dual
  human approval, atomic replay safety, IDOR 403 and shared-room access.
- Deny-all direct Firestore rules and a synthetic demo boundary that excludes
  every production-namespace record.

Historical evaluation evidence for the original coordination engine remains
separate. The corrected product has three fresh approval-boundary runs and one
real human-approved production commit, recorded without rewriting the baseline.

## Testing instructions

1. Open the public URL and click **Reset Demo**; the empty composer appears.
2. Enter the sample ICML need and select **Let Qi Agent draft the post**.
3. Review the three privacy sections, edit if desired, and publish.
4. Start monitoring. Watch request progress in Overview and optional Network /
   Audit tabs. Typical live execution takes under 90 seconds.
5. Inspect the exact approval contract. If its hold expired, choose **Revalidate
   offer**; an expired proposal is refused.
6. Only if you intend to create the synthetic internal demo match, select
   **Approve exact effect**. No payment or booking occurs.
7. Confirm both posts close and relationship/memory provenance appears after
   refresh.
