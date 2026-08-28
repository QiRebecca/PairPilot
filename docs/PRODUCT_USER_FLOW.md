# Product user flow

## 1. Empty state

`Reset Demo` removes mutable Qi/workflow state and returns to the composer. Qi
has no goal and no post. Maya and Lena each own one synthetic `OPEN` ICML
roommate post; Alice remains a trusted introducer and owns no candidate post.

## 2. Describe once

The user enters a natural-language need. In the demo:

> Find me a female roommate for ICML in Seoul from July 6 to July 10. Quiet
> overnight compatibility matters, partial overlap is okay, and do not exceed
> $70 additional cost.

This text is owner-private input, not a public post.

## 3. Live agent draft

Qi Agent uses Google ADK and `gemini-3.7-flash` structured output to create:

- a public title, summary, event, location, dates, and public requirements;
- agent-only quiet-fit importance, overlap permission, and maximum cost;
- protected-reference count without protected content;
- per-field provenance and uncertainties.

If live generation fails validation, the request fails safely. There is no
hardcoded draft fallback.

## 4. Review and publish

The review surface separates information into:

1. **Public post** — visible in the Intent Registry.
2. **Shared only with personal agents** — used within bounded negotiation.
3. **Protected and never sent** — count/reference only, never raw content.

The user can edit core fields. Publishing changes the Qi post from `DRAFT` to
`OPEN` and emits `intent.published` idempotently.

## 5. Agent-operated marketplace

Qi Agent searches public `OPEN` intent posts by intent type, location, date
overlap, capacity, and expiry. It can also inspect Alice relationship memory
and request an introduction to Maya's specific post. Both paths converge on a
single canonical intent-pair session, preventing duplicate negotiations.

## 6. Intent-scoped coordination

Every A2A request and response contains source intent, target intent, and pair
session identifiers. Peer claims remain reported claims. The privacy guard
allows only minimum-necessary reformulated information and blocks raw protected
memory.

Gemini chooses whom to contact, what to ask, how to evaluate the reports, and
when to propose. Infrastructure calculates costs and enforces the user's
published maximum. A `$62` compromise is allowed under `$70` but not `$50`.

## 7. Hold and exact approval

After both agents accept a versioned proposal, infrastructure reserves one unit
of capacity on that intent pair for 15 minutes. The approval contract displays
candidate, shared and solo dates, cost and maximum, terms, uncertainty,
recommendation, disclosure scope, proposal version, and expiry.

The agent cannot approve. If only the hold expires while the proposal and both
acceptances remain current, the user must explicitly choose **Revalidate
offer**. An expired proposal is never revived.

## 8. Atomic result

Exact human approval causes one preconditioned Firestore commit to:

- create one match;
- change Qi and Maya posts to `MATCHED`, consume capacity, and close contacts;
- release other sessions and holds touching either matched post;
- commit the proposal, run, hold, and approval request;
- create the Qi–Maya relationship with provenance;
- credit Alice only if her introduction was used;
- create a scoped, editable, non-authoritative memory;
- persist `match.committed` and two `intent.matched` outbox events.

Refresh reads the committed state from Firestore. Duplicate approval returns
the existing match rather than duplicating any effect.
