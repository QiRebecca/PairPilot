# Agent authenticity audit

Audit date: 2026-08-28. Scope: `packages/`, `services/`, `infra/`, and `tests/`.
The audit used source inspection, targeted ripgrep searches, tests, Firestore
read-back, Cloud Logging, and live model-selected runs. It does not treat seeded
world facts, typed permissions, transport routing, deterministic cost math, or
authority validation as agent strategy.

## Outcome

No Critical or High authenticity issue remains in the audited source. The
orchestrator exposes tools and validates actions but does not choose contact
order, candidate outcome, negotiation result, or natural-language messages.
Development runs exhibited different tool orders, and live text was not found
as a source literal.

## Findings

| Severity | File and evidence | Impact | Fix or rationale | Verification |
|---|---|---|---|---|
| Medium, fixed | `workflow/golden_path.py`: the first implementation interpreted the 12-turn bound as 12 tool calls. | A valid live run reached a hold but could not select the approval tool. This constrained strategy through infrastructure rather than agent reasoning. | Split the limits into 12 model turns and 16 tool calls. The model still chooses every action. | A subsequent live run selected 13 tools in 7 model turns and constructed the full effect contract. |
| Medium, fixed | `workflow/golden_path.py`: relationship inspection initially required one exact internal context string. | Gemini supplied a natural business query and failed before it could reason over the graph. | Relationship inspection now enumerates only records visible to `qi-agent` and returns their stored contexts. The query no longer acts as hidden strategy. | Later runs selected the seeded Alice relationship from the returned graph. |
| Medium, fixed | `run_golden_path.py`: a timeout could overwrite `WAITING_FOR_HUMAN_APPROVAL` after the effect contract had already been persisted. | The observable run status could under-report a real approval boundary. | Preserve the approval boundary on cleanup and record `latency_to_boundary_ms` separately from cleanup latency. | Unit/static checks pass; fresh cloud re-verification remains required after transient Vertex throttling subsides. |
| Medium, mitigated | `a2a_client.py` and `run_golden_path.py`: Vertex returned real 429 resource-exhausted errors during multi-agent runs. | A live run may terminate before a decision even though no safety invariant failed. | Serialize peer model calls and add at most two exponential-backoff retries to both A2A and Qi model boundaries. No deterministic response or fallback is substituted. | One run recovered an Alice request after one retry; a later first-turn 429 failed safe with zero tool calls before the Qi retry patch. Fresh verification remains pending. |
| Low, accepted | `a2a_server.py` and `a2a_client.py` contain an agent-ID-to-card/route map. | A superficial scan could mistake name-based transport routing for name-based candidate selection. | Keep explicit routing because separate Agent Cards and endpoints are an A2A requirement. The map contains no score, acceptance, rejection, or candidate outcome. | No `if candidate.name == ...` or equivalent outcome rule exists. |
| Low, accepted | `agents/alice.py`, `agents/maya.py`, and `agents/lena.py` contain their scoped seeded facts. | Facts are deterministic inputs to independent agents. | This is the required seeded world, not a seeded workflow. Each agent still calls its own tool and generates its own `PeerDecision`; the executor validates but does not choose the action. | Live responses varied in wording and Alice decisions originated from the live model/tool session. |
| Low, accepted | `a2a_executor.py` restricts Alice to introduction actions and candidates to information/negotiation actions. | This is a name-aware authorization boundary. | Retain it as least-privilege tool permission. It prevents a roommate candidate from asserting introduction authority and never selects an allowed outcome. | Invalid cross-role actions fail closed; valid live exchanges persisted peer identity and model provenance. |
| Low, accepted | `workflow/golden_path.py` contains fixed goal dates, a $70 delegation ceiling, and a $124 deterministic room rate. | These values necessarily produce the required deterministic $62 result. | Retain as authoritative goal and cost inputs. The model chooses when and for whom to call the cost tool; math and authority are not delegated to the model. | Live run calculated 4 total nights, 3 shared nights, and $62 additional cost. |
| Informational | `config.py` defines a visibly named deterministic development mode. | A fallback could be misrepresented as live if selected silently. | Live mode is pinned to `gemini-3.7-flash`; no exception handler returns a scripted model result. Development mode is explicit and is not used by the judging path. | Live outputs and Firestore provenance record the exact model and execution mode. |

## Prohibited-pattern review

The audit searched for candidate-name conditions, fixed Maya/Lena outcomes,
replayed semantic events, hardcoded generated messages, silent fallbacks, mock
badges, and fabricated evaluation text. Candidate names occur in required seed
facts, peer identities, Agent Cards, tests, and human-readable descriptions.
They do not occur in a candidate-outcome branch.

The scheduler may detect progress, enforce bounds, persist state, retry a
throttled call, and stop safely. It does not select the next semantic action.
The Qi model selected different valid early trajectories in observed runs:

- relationship lookup → introduction → open discovery;
- relationship lookup → open discovery → introduction;
- concurrent candidate inquiries after either route.

These are development observations, not the required three-run evaluation.

## Remaining audit gates

- Run the patched workflow three fresh times after a reset before each run.
- Confirm at least two distinct valid trajectories and zero leakage.
- Audit the upcoming web service and UI for scripted events or fake live badges.
- Run a final source and Git-history secret scan before submission.
