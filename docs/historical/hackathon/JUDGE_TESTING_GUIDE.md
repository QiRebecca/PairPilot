# PairPilot judge testing guide

This is the public, credential-free guide for the frozen PairPilot V1
submission. Private prepared credentials are shared directly with authorized
judges and are never stored in Git.

## Access

- Production: <https://pairpilot-orchestrator-ew4hz5g3la-nw.a.run.app/>
- Recommended account: the **pre-populated requester** labelled
  **Controlled test account** in the private judge instructions.
- Alternate accounts: a clean fresh-start requester and a candidate for the
  dual-approval step.

All prepared accounts are already Firebase-authenticated identities in an
email-verified test state. A judge does not need access to our inbox, Firebase
Console, Google Cloud project, or any global reset operation.

## Recommended 3–5 minute path

1. Sign in with the pre-populated requester and open **My Agent**.
2. Confirm that prior messages remain in the one persistent conversation. Send
   a natural-language follow-up such as “Which active candidate currently looks
   strongest, and what is still uncertain?”
3. Wait for the live response. Expand **Response audit** below the Agent message
   and verify a fresh live model source, model ID, invocation ID, latency,
   token counts when returned, and tool count.
4. Open the existing active request from its chat card or context rail. The
   same Agent conversation and history should remain visible.
5. Inspect the authoritative Post state. Use **View in Explore**, open its
   detail, and try a text, tag, or Community filter. Public fields should be
   visible; private chat and private instructions should not.
6. Return to the request and inspect the dynamically ranked candidate pool.
   Open at least two **Agent Rooms** and compare the independently authored A2A
   transcript, evidence, conflict, and uncertainty.
7. Open **Matches**, **Network**, and **Memory**. Confirm that the completed
   Match unlocks a Shared Room, the relationship cites committed outcome
   provenance, and proposed Memory is not usable until confirmed.
8. If a current proposal is prepared, approve it as the requester. The UI must
   report that the first approval is waiting; it must not create a Match.
9. Sign out, sign in with the prepared candidate account, open the same proposal
   from that user's perspective, and approve the identical current version.
10. Confirm that the second approval creates one Match, closes or consumes the
    relevant Posts, and unlocks the participant-scoped Shared Room.

Live model calls commonly complete in 10–90 seconds. If a turn reports a model
failure, PairPilot deliberately saves no fabricated assistant answer; retry the
turn once. The prepared path is designed to avoid waiting for an entire new
market cycle.

## Fresh-start path

Use the clean requester account when you want to evaluate creation rather than
the complete downstream state:

1. Tell the Personal Agent a specific need, including time, place and useful
   preferences.
2. Answer any necessary clarification in the same conversation.
3. Inspect the Agent-created Task and Post preview card.
4. Revise, cancel, continue chatting, or choose **Approve & publish**.
5. Navigate away and back. The conversation, saved draft, and authoritative
   publication status should persist.
6. Open the published Post in Explore. Background candidate discovery can take
   longer than the prepared 3–5 minute path because it runs through real
   Gemini/ADK and Pub/Sub processing.

## What proves the Agent is live

For any successful assistant message, expand **Response audit**. PairPilot
persists and displays the response classification, exact model, ADK invocation,
latency, token counts when Vertex returns them, and tool count. The interface's
live badge is derived from persisted message provenance rather than static
marketing copy.

Agent Rooms provide a second proof surface. Their messages are attached to
separate acting Personal Agents and canonical source/target Intent-pair
sessions. Public Post content and peer statements are visible there; the other
person's private conversation is not.

## Expected authority and privacy behavior

- A Post is not discoverable until it is authorized and `OPEN`.
- A published Post remains authoritative after navigation or refresh.
- The first human approval waits for the other person.
- Only two approvals of the same current proposal version can create a Match.
- Login email is never automatically shared; optional contact cards are
  match-scoped and revocable.
- Proposed Memory is inert until confirmed by its owner.
- One account cannot open the other user's private Task, conversation, Memory,
  or non-participant Room.
- PairPilot performs no booking, payment, identity verification beyond email,
  or autonomous final commitment.

## Controlled data and reset policy

All visible demo participants are labelled **Controlled test account** or
**Demo participant**; they are not represented as organic users. Judges should
not delete accounts or attempt a global reset. If the prepared workspace has
been consumed, contact the team using the private support note. The team will
reset only the isolated judge cohort without changing other users or frozen
production behavior.

## Further evidence

- [V1 live acceptance](V1_LIVE_ACCEPTANCE_REPORT.md)
- [V1 completion matrix](V1_PRODUCT_COMPLETION_MATRIX.md)
- [Real Agent response provenance](REAL_AGENT_RESPONSE_PROVENANCE.md)
- [Architecture](../ARCHITECTURE.md)
- [Prior-work disclosure](../PRIOR_WORK.md)
