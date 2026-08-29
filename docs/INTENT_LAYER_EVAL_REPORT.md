# Corrected intent-layer live evaluation

Evaluation date: 2026-08-29. Target: tagged `intent-v2` Cloud Run revisions.
All runs used the actual draft, review payload, publish endpoint, public SSE,
live Vertex AI `gemini-3.7-flash`, Google ADK, authenticated A2A, and Firestore.
The historical `docs/EVAL_REPORT.md` remains unchanged baseline evidence.

## Three approval-boundary runs

Each run began with reset, generated a live structured Qi draft from current
input, published a new Qi `OPEN` post, and terminated at the human boundary.
No automation created approval or match during these evaluations.

| Run | Discovery trajectory | Latency | Tools | Intent-scoped messages | Token events / total | Result |
|---|---|---:|---:|---:|---:|---|
| `7e422a20-7147-4032-8536-ea998fb22205` | OPEN registry → Maya/Lena direct | 73.298 s | 9 | 6 | 7 / 21,353 | proposal + hold; approvals 0; matches 0 |
| `34a5390f-6421-4eb7-9984-9c63fea661db` | OPEN registry → Maya/Lena direct | 51.987 s | 9 | 6 | 7 / 20,984 | proposal + hold; approvals 0; matches 0 |
| `ab105b82-d399-4327-96ee-d162bbeeec7d` | Alice warm introduction + OPEN registry | 55.778 s | 11 | 8 | 11 / 31,948 | proposal + hold; approvals 0; matches 0 |

All six/eight messages per run carried source intent, target intent, and
canonical pair-session identity. Maya's proposal acceptance referenced the
current version. The third trajectory used Alice and persisted
`introductionUsed=true`, proving relationship memory influenced planning while
open-post discovery remained available. The first two valid runs chose a direct
path, so at least two distinct valid trajectories were observed.

## Dynamic input evidence

Two no-write live Qi drafting calls extracted current user input rather than a
fixed goal:

- `$70` became the published delegated maximum and allowed the deterministic
  `$62` partial-overlap compromise.
- `$50` was extracted as `explicit_user_input`; the same `$62` plan is rejected
  by the authority unit test and cannot silently use the old `$70` value.
- Unqualified July 6–10 became 2026 dates, with the year explicitly marked as
  `agent_inference` and surfaced in `uncertainties`.

## Privacy and authority evidence

- Search returned only public fields from current `OPEN`, non-expired,
  capacity-bearing posts; no private profile drove discovery.
- Public state and intent endpoints excluded raw goals, agent-only constraints,
  protected references, and owner-private context.
- Peer compatibility statements remained `REPORTED_CLAIM`.
- The protected raw sleep fact did not appear in public posts or A2A messages.
- Every approval-boundary run had exactly one proposal and one intent-capacity
  hold, with zero approvals and zero matches.
- All valid runs terminated inside the 90-second bound.

## Positive production run

Run `47fc6638-e2b5-4253-8b5c-bee46e07278d` followed the warm-introduction
trajectory and reached the boundary in 68.021 seconds with 11 tools, nine token
events, and 27,568 total tokens. A real operator then approved the visible
current effect. Atomic and idempotency evidence is in
`docs/POSITIVE_COMMIT_VERIFICATION.md`.

## Honest failure history

Several early tagged attempts failed safely due to tagged-URL token audience,
schema-empty peer output, or asymmetric introduction claims. They created no
approval or match. Each failure produced a bounded observable error and led to
the fixes recorded in `docs/INTENT_LAYER_DEPLOYMENT_REPORT.md`; none reached
production traffic before correction.
