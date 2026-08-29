# PairPilot public-beta readiness

Status: **candidate implementation; launch gate not passed**

## Implemented and automated

- Firebase Web SDK auth provider, session restoration, fresh bearer tokens and clean sign-out state reset
- Firebase Admin token verification with revocation/disabled checks
- one deterministic Personal Agent per verified UID
- owner-scoped tasks, conversations, private intent data, decisions, memory and relationships
- real public post projections with pause/close and blocked-user filtering
- asynchronous `intent.published.v2` event and authenticated Pub/Sub push worker
- per-task and per-intent-pair crash-recoverable leases
- arbitrary user-owned Agent loading and two independent bounded ADK/Gemini negotiation turns
- dual Agent acceptance, dual current-version human approval and atomic match commit
- participant-authorized rooms, authored messages, leave, block and report
- account export and deletion social-shutdown model
- direct Firestore browser access denied by default

## Blocking public launch

- deploy and verify the `multi-user-beta` no-traffic revision;
- exercise two controlled, email-verified Firebase accounts;
- verify real email verification/password-reset delivery and clean return links;
- capture two-browser isolation and two-human match evidence;
- confirm Pub/Sub OIDC push and real ADK/Gemini logs on the candidate;
- enable required Google-account MFA for continued Firebase Console access;
- complete final secret scan and documentation/submission updates.

Production traffic must remain on the previous revision until every item above passes.
