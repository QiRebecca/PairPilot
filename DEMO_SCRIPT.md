# Four-minute demo script

Target length: **3:55**. Record one uninterrupted live run. If accelerated,
label the speed and preserve the full continuous execution.

## 0:00–0:25 — The friction

“Finding a conference roommate is not a search result. It is repeated social
coordination: who to trust, what to disclose, changing dates, compatibility,
negotiation, and commitment.”

Show the PairPilot network at its reset baseline.

## 0:25–0:45 — One intent

Show the goal once. Point to:

- quiet overnight fit as priority 1;
- `$70` delegated boundary;
- one protected private fact;
- human approval required for commitment.

“The private fact never leaves Qi Agent. Peers receive only the minimum-
necessary compatibility question.”

Click **Start live run**.

## 0:45–1:25 — Relationship-aware autonomy

As the graph activates:

“This is live `gemini-3.7-flash` through Google ADK. Qi Agent chooses its tools
and communication; the UI is reading Firestore-backed SSE snapshots, not
playing a recording.”

Show Qi inspecting its Alice relationship, discovering candidates, and asking
Alice Agent for an introduction. Point to the trusted violet edge and warm
introduction.

## 1:25–2:05 — Direct agent communication

Show the real A2A channel:

- Alice's introduction;
- Maya's reported quiet routine;
- Lena's reported late calls.

“Alice, Maya, and Lena are independent ADK personal agents behind separate A2A
1.0 cards and endpoints on a private Cloud Run service. Peer claims stay marked
as reports—not verified truth.”

Show Lena withdrawal and Maya continuing.

## 2:05–2:35 — Agent-created solution

Show the deterministic calculation:

```text
4 total nights · 3 shared nights · $62 extra < $70
```

“The model chose when and for whom to calculate. Infrastructure owns the math
and current availability.”

Show proposal v1, Qi acceptance, Maya A2A acceptance, and soft hold.

## 2:35–3:05 — Human-governed commitment

Pause on the effect contract. Read the candidate, dates, cost, uncertainty,
disclosure, version, and hold expiry.

“The agents can search, contact, negotiate, and hold. They cannot commit.”

Click **Approve exact effect** only for the continuous run being recorded.
Show commit revalidation and the committed state. If the hold has expired,
reset and record a fresh continuous run; never splice a different approval.

## 3:05–3:30 — Relational learning

Open **Relationship memory**. Show:

- new Qi → Maya successful-coordination relationship;
- Alice's successful-introduction counter;
- provenance event ID;
- scoped editable inference that Qi accepted partial coverage for quiet fit.

“The network grows only from a committed event.”

## 3:30–3:55 — Google Cloud proof and closing

Show the `.run.app` URL, then Cloud Run services, the exact run ID in Cloud
Logging, the committed Firestore document, and the architecture diagram.

“PairPilot runs on Cloud Run, Vertex AI, Firestore, Pub/Sub, Cloud Build, and
Cloud Logging.”

Close:

“Humans express intent. Personal agents build the relationships and do the
coordination. Infrastructure enforces truth, privacy, and authority.”
