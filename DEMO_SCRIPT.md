# Four-minute real multi-user demo script

Use two already verified controlled test accounts in separate browser contexts.
Never show or paste passwords, ID tokens, private email addresses or Secret
Manager values. Keep the old named-person flow only as an optional synthetic
walkthrough.

## 0:00–0:25 — Product and trust boundary

Open the public landing page. Show **Create your Personal Agent**, **Sign in**,
and **See the synthetic demo**. State that the production app has real isolated
users, while the demo route contains synthetic people.

## 0:25–0:55 — User A tells their Agent

Sign in as Test User A. In `/app/agent`, describe an ICML roommate need. Show
that the Agent creates a private request first, with event, city-level location,
dates and safe-to-publish requirements separated from the raw goal.

Review the public title and summary, then click **Approve post & publish**.
Point out that the browser sends a fresh Firebase ID token and cannot supply an
authoritative owner UID.

## 0:55–1:25 — A real second user

Switch to Test User B's browser context. Show a different display name,
different Personal Agent ID and no User A private task. Publish a compatible
request. In Explore, show only public, human-approved projection fields—never
emails, private goals or Agent-only boundaries.

## 1:25–2:10 — Asynchronous user-owned Agents

Briefly show Cloud Logging: `intent.published.v2` reaches the OIDC-authenticated
Pub/Sub worker. The generic runtime loads A and B's separate Agent policies and
runs two bounded Google ADK / `gemini-3.7-flash` turns. Show the Agents-only
room messages with explicit Agent authorship and task/intent scope.

## 2:10–3:00 — Two humans, one current version

In User A's decision, show candidate, shared dates, disclosure, uncertainty,
hold expiry and proposal version. Approve. Show
**Waiting for the other person** and confirm there is still no match.

Switch to User B. Show B's separate owner-perspective effect contract and
approve the same version. The match now commits exactly once; both posts become
`MATCHED`.

## 3:00–3:35 — Shared result, private graphs

Open the shared room in both contexts. Send one clearly human-authored message.
Show that each user has an independent relationship entry and private memory
surface. Mention participant membership, block/report, leave-room, export and
account-deletion controls.

## 3:35–4:00 — Proof and limits

Show the zero-traffic candidate revision, Firestore production namespace,
Pub/Sub subscription, Firebase Email/Password method and test report. State the
limits plainly: email verification is not identity verification; PairPilot
does not book, process payments, or guarantee compatibility or safety.
