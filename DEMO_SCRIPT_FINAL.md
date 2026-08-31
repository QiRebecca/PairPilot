# PairPilot Final Demo Script

Target length: **3:50** (acceptable range: 3:40–3:55)

Track: **Taskmaster**

All timestamps below are **planned** until the final exported video is reviewed.
Use controlled test accounts only and never show credentials.

## Before recording

- Set the browser to 1440×900 and 100% zoom.
- Sign in to the pre-populated controlled requester from the private judge guide.
- Keep the prepared candidate approval account signed in only in a second
  private/incognito window; crop all browser profile chrome.
- Open the requester at **My Agent** with its persistent conversation, active
  request, three candidates and Agent Rooms ready.
- Prepare tabs for `/api/health`, production Cloud Run revision `00042-rob`, a redacted
  Cloud Logging invocation and `docs/architecture.png`.
- Hide email addresses, passwords, tokens, UIDs, contact details and private
  instructions. Display names must say controlled/simulated/demo participant.
- Rehearse once. Do not use a live path whose result is uncertain; use the
  prepared authoritative state and demonstrate one safe live chat turn.

## Planned narration and action

### 0:00–0:20 — Problem

**Screen:** Landing page, then authenticated My Agent.

**Narration:**

“Finding the right person for a real-world plan is repetitive. You post in
several places, answer the same questions and manually compare people.
PairPilot turns that work into an agent-operated marketplace. Every user owns a
persistent Personal Agent, while the humans keep final commitment authority.”

### 0:20–0:50 — Talk to one persistent Personal Agent

**Screen:** Send a short follow-up in the existing requester chat. Keep earlier
messages visible. Open the inline request card and return without changing to a
different conversation.

**Narration:**

“I simply tell my Agent what I need. It remembers this conversation, asks only
for missing constraints and keeps the same chat even while it works on a
specific task. This is a live Gemini 3.7 Flash turn through Google ADK; the
model, session, invocation and tool provenance are persisted.”

### 0:50–1:15 — Review and publish the Agent-drafted Post

**Screen:** Show the inline Post preview, public description and tags. Briefly
show the private Agent context as a separate protected section. Approve/publish,
or use the already-published controlled Post if a live mutation would make the
demo brittle. Open it in Explore detail.

**Narration:**

“The Agent turns the conversation into a public Post. I can revise, continue
chatting or approve it. Private instructions stay in the task workspace and do
not enter the marketplace. Publication changes authoritative Firestore state,
and the Post is searchable and shareable only in its eligible community.”

### 1:15–1:50 — Multiple real Agent conversations and ranking

**Screen:** Open the requester’s three ranked candidates. Open two different
Agent Rooms and show separate messages/evidence. Return to the ranking and show
rank-change provenance.

**Narration:**

“Publishing starts background discovery. This request has three independently
owned candidate Agents and separate rooms. The Agents exchange task-scoped
messages over A2A, not hardcoded replies. PairPilot keeps verified facts,
peer-reported claims, conflicts and uncertainty separate, then dynamically
reranks candidates as evidence changes.”

### 1:50–2:15 — Ask why and give a private instruction

**Screen:** Ask the Personal Agent why the first candidate ranks highest. Show
the private-instruction control, using a safe demo canary. Then show that the
public Post/Agent Room does not contain it.

**Narration:**

“I can ask why a candidate is first and add a private instruction in the same
chat. The Agent can use that preference internally, but PairPilot’s public and
A2A projections exclude the private canary and contact details.”

### 2:15–2:35 — Later Post triggers automatic reevaluation

**Screen:** Show the Late Candidate Post, a corresponding in-app notification
or rank event, and the refreshed ordering. If the event has already run, show
its persisted before/after evidence rather than republishing.

**Narration:**

“PairPilot keeps working while I am away. A later compatible Post is consumed
through authenticated Pub/Sub and the periodic reconciliation safety net. It
triggers reevaluation and a new rank event without reopening the request.”

### 2:35–3:05 — Two humans independently approve

**Screen:** Requester approves the current proposal version; show
`WAITING_FOR_OTHER_HUMAN`. Cut to the prepared candidate account and approve the
same version. Cut back to the requester’s committed Match.

**Narration:**

“Agents can recommend and prepare a proposal, but they cannot make the final
social commitment. The requester approves version one and the system waits.
The candidate independently approves the same current version. Only then does
one atomic transaction create the Match and unlock the shared room.”

### 3:05–3:30 — Match, Shared Room, Network and Memory

**Screen:** Show Match, the simulated participant’s Shared Room message,
Network relationship provenance and confirmed Memory.

**Narration:**

“The committed Match unlocks a human room and scoped contact exchange. The
outcome creates a provenance-backed relationship in Network. The Agent may
propose reusable Memory, but it becomes global only after I confirm it.”

### 3:30–3:55 — Google Cloud proof and architecture

**Screen:** `/api/health`; Cloud Run `pairpilot-orchestrator-00045-tig` and Peer
`00022-seh`; a redacted invocation log; Firestore collection names; architecture
diagram.

**Narration:**

“PairPilot runs on Cloud Run with Firebase Authentication, Firestore,
authenticated Pub/Sub and Cloud Scheduler. Personal and peer Agents use Google
ADK with Vertex AI Gemini 3.7 Flash. The submitted revision passed live
multi-user, A2A, dual-approval, privacy and persistence gates. PairPilot: tell
your Agent what you need, and come back for the decision that matters.”

## Recording integrity

- Do not claim organic users or marketplace scale. Say “controlled test
  accounts” and “simulated demo participant”.
- Do not claim payment, booking, government identity verification or autonomous
  final commitment.
- Do not show a staged typing animation as proof of a live model. Correlate the
  successful UI turn with persisted provenance and Cloud Logging.
- Do not display hidden chain-of-thought. Show model/tool/session metadata and
  user-visible explanations only.
- After export, record the actual start/end timestamp for every shot in
  `docs/FINAL_EVIDENCE_INDEX.md`.
