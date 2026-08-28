# CLI golden-path report

Status on 2026-08-28: the live workflow has reached and persisted the human
approval boundary. Atomic commit is implemented and proven to reject a cloud
commit without approval. A fresh post-retry run is still required before Gate 4
is marked fully complete.

## Strongest live run

Run ID: `3244ae4c-8d9d-4ea8-80f3-c98899dc48d5`

The single high-level goal was supplied once to a live `gemini-3.7-flash` Qi
Agent. The model selected this observable tool order:

1. inspect the contextual relationship network;
2. discover open ICML agents;
3. ask Alice for a warm introduction;
4. contact Lena and Maya through their independent A2A endpoints;
5. withdraw from Lena based on her reported overnight routine;
6. continue with Maya based on her reported quiet routine;
7. calculate Maya's partial-overlap cost;
8. create proposal version 1;
9. record Qi Agent's acceptance;
10. send the proposal for Maya Agent's independent decision;
11. place a soft hold after Maya accepted version 1;
12. request the user's approval with a complete effect contract.

The run used 13 tool calls across 7 live Qi model turns. The two candidate
inquiries were model-selected in the same turn and executed through a bounded
peer semaphore. No source file encodes this sequence.

## Verified state and evidence

- Alice returned an `INTRODUCTION_RESPONSE` identifying Maya through a typed
  claim.
- Lena returned an `INFORMATION_RESPONSE`; the late-call routine remained a
  `REPORTED_CLAIM`, never a verified fact.
- Maya returned an `INFORMATION_RESPONSE` with reported dates and routine.
- Deterministic cost output was 4 total nights, 3 shared nights, `$62`
  additional cost, and a `$70` delegated maximum.
- Maya returned `ACCEPTANCE` with proposal version 1 echoed in the A2A envelope.
- The hold bound the same proposal ID and version and was active when the
  effect contract was built.
- The effect contract listed identity summary, shared dates, solo date, cost,
  terms, uncertainty, recommendation, disclosure scope, protected scope,
  version, hold expiry, and current availability.
- No approval or match was created by the agent.

The runner originally reported `TIMEOUT` during post-boundary telemetry cleanup
at approximately 91 seconds even though the approval request and effect
contract had been persisted. This status race is fixed: cleanup no longer
overwrites an already reached approval boundary, and time-to-boundary is now
reported separately.

## Failure evidence retained during development

- Two early runs failed closed because a relationship tool treated a natural
  query as an internal enum. The API was generalized to enumerate visible
  contextual relationships.
- One run made five strategic tool calls and then failed on a peer Vertex 429.
- One fresh post-reset run received a Vertex 429 before its first tool call and
  failed safe with zero business action.
- Peer and Qi model boundaries now use bounded retries only; no scripted result
  or silent fallback is returned.

## Commit boundary

`approve_golden_path.py` reloads the current effect contract and requires the
user to type `APPROVE VERSION N`. The Firestore commit then revalidates proposal
version and expiry, active hold, current availability, both agent acceptances,
human approval version, disclosure hash, and match idempotency. Thirteen
preconditioned writes atomically create the match and grow relationship/memory
state. A live negative check without a human approval returned a blocked
authority result; no match was written.
