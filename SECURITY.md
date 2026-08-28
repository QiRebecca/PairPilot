# Security and privacy

## Security posture

PairPilot is a synthetic, non-payment hackathon demo. It does not book a hotel,
verify a real identity, or contact public users. Nevertheless, its authority
boundaries are designed as production controls rather than prompt promises.

## Authentication

- Developers use Google Application Default Credentials.
- Cloud Run uses `pairpilot-runtime` without a downloadable key.
- The public orchestrator is anonymous by design for judges.
- The peer service is private. Only the runtime service account has
  `roles/run.invoker`; the orchestrator fetches a short-lived audience-bound
  identity token.
- No Gemini API key, service-account JSON, billing identifier, coupon, access
  token, refresh token, or account email belongs in the repository.

## Authorization

The model cannot commit, approve, read arbitrary collections, change delegated
authority, or call a target that has not been discovered or introduced.
Infrastructure validates caller, target, state, visibility, typed arguments,
message bounds, proposal version, expiry, hold, current availability, both
agent acceptances, disclosure hash, and idempotency.

## Privacy

Private agent profiles are isolated by owner. Outbound disclosure uses scoped
context, typed memory references, a deterministic privacy guard, and
minimum-necessary reformulation. Public APIs return a protected count, never
raw private content. Peer messages are untrusted and cannot rewrite system
instructions or grant authority.

## Public-demo abuse controls

- one active run per instance;
- one Cloud Run instance maximum;
- 12 starts per UTC day in a Firestore ledger that Reset cannot delete;
- per-instance request rate limit;
- 12 model turns, 16 tools, two candidates, four messages per pair, two retries,
  and a 90-second decision bound;
- scale to zero when idle.

## Reporting a vulnerability

Do not include secrets or personal data in a report. Open a private security
report with the repository owner and include the affected route, expected
authority rule, minimal reproduction, and observed result.
