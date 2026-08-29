# PairPilot real multi-user E2E report

Status: **AUTHENTICATED API PATH PASSED; EMAIL-LINK/BROWSER GATE REMAINS**

Automated two-principal tests currently prove separate provisioning, private bootstrap isolation, real public-post projection, two user-owned Agent identities, task/pair leases, two separate effect contracts, one-sided approval waiting, second-sided atomic commit, exactly-once replay behavior, post matching, room membership and independent relationship records.

On 2026-08-29, two independently authenticated Firebase accounts with distinct verified UIDs completed the candidate API path. Random passwords were generated in process, stored in Google Secret Manager, and never printed, documented, or committed.

## Passed candidate run

- Candidate revision: `pairpilot-orchestrator-00017-juz` at zero production traffic
- Test User A UID: `TH6daBdwmLQPeHA0noJVGpAnGC53`
- Test User B UID: `TUQWZjC3yOSxYQHePig3QzF7Mgj1`
- Agent A: `agent_6748a4b839dbb4b856d92762`
- Agent B: `agent_4469bd38b8d4095cf1ae9f7c`
- Task A: `task_53380c153d49437997f9195367aa5bc8`
- Task B: `task_a27a9b7164f64db99c9d41966c453377`
- Proposal/version: `proposal_20c80908810d88bb64b903ad`, version `1`
- First approval: `WAITING_FOR_OTHER_HUMAN`; no match existed
- Second approval: `MATCH_COMMITTED`
- Duplicate approval: returned the same committed match
- Match: `proposal_20c80908810d88bb64b903ad`
- Shared room: `room_91f89b787e4a7dad54bde59a`
- Cross-user private task read: HTTP `403`
- Both posts: `MATCHED`
- Both relationship projections: present and independently owner-scoped
- Public/room responses: no email or internal `participant_uids`

The first Agent attempt safely produced no proposal; a valid at-least-once redelivery completed both real ADK/Gemini turns. The worker now schedules at most one explicit retry for a failed or declined model turn and persists a non-sensitive failure event.

## Required candidate run

- [x] Two Firebase-authenticated, verified UIDs sign in independently.
- [x] Both complete onboarding and receive different Agent IDs.
- [x] Both publish compatible OPEN posts.
- [x] Pub/Sub invokes the OIDC-authenticated task worker.
- [x] Both generic ADK/Gemini Personal Agent turns accept the current reversible proposal.
- [x] User A approves; status remains `WAITING_FOR_OTHER_HUMAN`.
- [x] User B approves; one match commits exactly once.
- [x] Both posts become `MATCHED`.
- [x] Both users access the shared room and independent relationship view.
- [x] Cross-user private task attack returns 403 without private detail; automated IDOR tests cover the wider matrix.
- [ ] Sign-out A, sign-in B in the same physical browser shows no A state.
- [ ] Provider-delivered verification and reset links return correctly while signed out.
- [ ] Capture non-sensitive screenshots in two visible browser contexts.

Candidate URLs, non-sensitive run IDs and screenshots will be added only after the run actually occurs.
