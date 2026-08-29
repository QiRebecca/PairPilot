# PairPilot real multi-user E2E report

Status: **NOT YET PASSED**

Automated two-principal tests currently prove separate provisioning, private bootstrap isolation, real public-post projection, two user-owned Agent identities, task/pair leases, two separate effect contracts, one-sided approval waiting, second-sided atomic commit, exactly-once replay behavior, post matching, room membership and independent relationship records.

This is not a substitute for two independently authenticated, email-verified Firebase accounts.

## Required candidate run

- [ ] Test User A signs up or signs in in browser context A.
- [ ] Test User B signs up or signs in in browser context B.
- [ ] Both emails are provider-verified; no password is logged or documented.
- [ ] Both complete onboarding and receive different Agent IDs.
- [ ] Both publish compatible OPEN posts.
- [ ] Pub/Sub invokes the authenticated task worker.
- [ ] Both generic ADK/Gemini Personal Agent turns accept the current reversible proposal.
- [ ] User A approves; status remains `WAITING_FOR_OTHER_HUMAN`.
- [ ] User B approves; one match commits.
- [ ] Both posts become `MATCHED`.
- [ ] Both users open the shared room and their independent relationship view.
- [ ] Cross-user task, private intent, conversation, approval and room-ID attacks return 403/404 without private detail.
- [ ] Sign-out A, sign-in B in the same browser shows no A state.
- [ ] Verification and reset links return correctly while signed out.

Candidate URLs, non-sensitive run IDs and screenshots will be added only after the run actually occurs.
