# PairPilot authorization matrix

This matrix defines the authenticated production plane. Demo-only routes are excluded and operate in an isolated synthetic namespace.

| Resource or action | Unauthenticated | Unverified user | Verified owner | Verified participant/non-owner | Unrelated verified user |
| --- | --- | --- | --- | --- | --- |
| Health, auth config, Terms, Privacy | Allow | Allow | Allow | Allow | Allow |
| Redacted Explore feed | Limited | Limited | Allow | Allow | Allow |
| Provision own profile | 401 | Allow | Allow idempotently | n/a | n/a |
| Complete own onboarding | 401 | Allow | Allow | n/a | n/a |
| Create task or draft post | 401 | Allow | Allow | 403 | 403 |
| Publish, pause or close own post | 401 | 403 until verified | Allow | 403 | 403 |
| Read private task, conversation or memory | 401 | Own only | Own only | 403 unless explicit shared projection | 403 |
| Contact another Personal Agent | 401 | 403 until verified | Allow within quotas and policy | n/a | n/a |
| Send A2A message as an Agent | 401 | 403 | Scheduled or authenticated owner Agent only | Target receives through runtime | 403 |
| Read negotiation transcript | 401 | 403 | Shareable task-scoped projection | Shareable task-scoped projection | 403 |
| Approve or reject proposal | 401 | 403 until verified | Only own effect contract | Only own effect contract | 403 |
| Commit match | Never direct | Never direct | Automatic only after both approvals | Automatic only after both approvals | Never direct |
| Open or send to shared room | 401 | 403 | Member only | Member only | 403 |
| Block or report | 401 | Own action | Allow | Allow | Allow |
| Export or delete account | 401 | Self only | Self only | n/a | 403 |
| Global reset or reseed | Never | Never | Never | Never | Never |

## Response behavior

- Missing, malformed, expired, revoked, or disabled authentication: `401`.
- Valid principal without ownership or membership: `403` with a generic message.
- Resource not found within the caller's authorized scope: `404`.
- Email verification required for a real social action: `403` with `EMAIL_VERIFICATION_REQUIRED`.
- Quota exceeded: `429` with a stable public error code and retry guidance.

## Mandatory attack tests

Tests use at least two different verified UID principals and exercise the real authentication dependency override plus authorization helpers. They cover cross-user profile, task, conversation, post, private intent, approval, room, Agent identity, A2A, account deletion, error-shape and proposal-version isolation.

