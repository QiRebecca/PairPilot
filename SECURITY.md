# Security and privacy

## Security posture

PairPilot has a real multi-user candidate and a separate synthetic sandbox. It
does not verify identity beyond Firebase email verification, book a hotel,
process payment, or guarantee safety or compatibility. Public-beta authority
boundaries are enforced by Firebase identity, server-side ownership checks,
two-sided approval and atomic Firestore preconditions—not prompt promises.

## Authentication

- Developers use Google Application Default Credentials.
- Cloud Run uses `pairpilot-runtime` without a downloadable key.
- Landing assets, auth bootstrap, legal pages, health and the explicit demo
  sandbox are public. Every production state-changing route and every private
  read requires a Firebase Bearer token.
- Firebase Admin verifies signature, expiry, disabled state and revocation.
- The verified UID—not browser-supplied email, owner UID or Agent ID—is the
  principal for authorization.
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
agent acceptances, both independent human approvals, disclosure hash, and
idempotency. Cross-user task reads and room-ID guessing are denied. Direct
browser Firestore rules deny all reads and writes.

## Privacy

Private agent profiles are isolated by owner. Outbound disclosure uses scoped
context, typed memory references, a deterministic privacy guard, and
minimum-necessary reformulation. Public APIs return a protected count, never
raw private content. Peer messages are untrusted and cannot rewrite system
instructions or grant authority.

## Public-beta abuse controls

- three active requests per UID;
- two concurrent negotiations and five new contacts per task;
- daily Agent-turn quota stored per UID;
- per-task and per-pair crash-recoverable leases;
- bounded one-time retry after a failed/declined model turn;
- per-instance request rate limit;
- scale to zero when idle.

The old global lock and reset exist only inside the isolated synthetic demo.

## Reporting a vulnerability

Do not include secrets or personal data in a report. Open a private security
report with the repository owner and include the affected route, expected
authority rule, minimal reproduction, and observed result.
