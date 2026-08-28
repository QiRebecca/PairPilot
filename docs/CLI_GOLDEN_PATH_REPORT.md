# CLI golden-path report

Status on 2026-08-28: **verified to the human approval boundary within the
required 90-second decision bound**. Atomic commit is implemented and proven
to reject a commit without approval. A positive live commit remains deliberately
unexecuted until the user approves the displayed effect contract.

## Verified live run

Run ID: `2598aaed-1b7b-4dee-97bd-7b2d150d9dde`

The single high-level goal was supplied once to a live
`gemini-3.7-flash` Qi Agent running through Google ADK. Gemini selected this
observable tool path:

1. inspect the contextual relationship network;
2. discover open ICML agents;
3. ask Alice Agent for a warm introduction;
4. contact Lena and Maya concurrently through their A2A endpoints;
5. withdraw from Lena based on her reported late-call routine;
6. calculate Maya's partial-overlap cost;
7. create proposal version 1;
8. record Qi Agent's acceptance;
9. send the proposal to Maya Agent;
10. place a soft hold and request human approval after Maya accepted.

The run selected 10 tools across 8 live Qi model turns. It reached
`WAITING_FOR_HUMAN_APPROVAL` in **81,398 ms** and completed outbox cleanup in
**84,267 ms**, with zero model retry and no error.

## Verified state

- Alice returned an `INTRODUCTION_RESPONSE` identifying Maya through a typed
  peer claim.
- Lena and Maya returned independent `INFORMATION_RESPONSE` messages.
- Peer claims remained `REPORTED_CLAIM`; they were never promoted to current
  authoritative facts.
- Deterministic output was 4 total nights, 3 shared nights, `$62` additional
  cost, and a `$70` delegated maximum.
- Maya returned `ACCEPTANCE` for the exact proposal version.
- The hold and effect contract referenced the same proposal ID and version.
- The contract showed identity, dates, cost, terms, uncertainty,
  recommendation, disclosure scope, protected scope, hold expiry, and current
  availability.
- Firestore contained no human approval and no match after the run.

## Performance correction

An earlier valid run reached both agent acceptances but timed out before the
hold because three peer inquiries were serial. The orchestrator now exposes a
single `contact_candidates` tool: Gemini still chooses the candidate IDs and
question, while infrastructure validates the list and runs at most two A2A
requests concurrently. This removed one model round and the serial peer delay
without encoding candidate outcomes.

## Failure evidence retained

- Early runs failed closed when a relationship tool rejected a natural query;
  the tool now enumerates only Qi-visible relationships.
- Vertex produced genuine 429 and empty-output failures during development.
  Bounded retry applies at model boundaries; no scripted fallback exists.
- `MINIMAL` thinking produced a Vertex 400 for the verified model. All agents
  now use the supported `LOW` level, covered by a regression test.
- One pre-batching run selected 11 tools and both agent acceptances but reached
  the 90-second wall before the hold. Its timeout was preserved honestly.

## Commit boundary

The CLI requires the exact phrase `APPROVE VERSION N`. The web control sends
the same current-version approval only after displaying the complete contract.
Commit then revalidates proposal version and expiry, active hold, availability,
both agent acceptances, human approval version, disclosure hash, and match
idempotency. Thirteen preconditioned Firestore writes atomically create the
match and relationship/memory updates. A live negative check without approval
was blocked and wrote no match.
