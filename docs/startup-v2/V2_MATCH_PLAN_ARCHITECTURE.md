# Startup V2 Match plan architecture

Updated: 2026-09-01

## Product contract

A Match is the durable, participant-scoped execution record created only after
the existing version-bound dual-human approval flow commits a proposal. It is
not a recommendation card and it does not expose login identity.

## Read model

- `GET /api/app/matches` returns only Matches containing the authenticated UID,
  grouped into Needs Action, Upcoming, In Progress, Completed, and Cancelled.
- `GET /api/app/matches/:id` requires participant authority and projects safe
  participant display names, the approved plan, Community, Shared Room, Contact
  Cards, change history, cancellation/backup state, and private outcome state.
- Internal participant and Contact Card owner UIDs are not returned.
- Canonical state derives from explicit terminal state plus scheduled start/end
  times, while mapping legacy `COMMITTED` and `MATCHED` values.

## Plan operations

- Calendar export produces an escaped UTC RFC 5545-style `.ics` artifact.
- A material change creates an immutable new change version and one owner-scoped
  Decision per participant. The current Match remains unchanged until both
  participants approve the exact same version.
- Cancellation records who cancelled, the reason and timestamp, releases future
  commitments, notifies both participants, appends relationship provenance, and
  can emit a durable backup-reactivation request.
- Backup activation is allowed only after cancellation and deterministically
  selects the best ranked candidate still in `BACKUP`.
- Completion is explicit and enables private outcome feedback.

## Contact, outcome, and safety boundaries

- Contact Cards are Match-scoped and field-by-field opt-in. Account login email
  is never used as a default contact field.
- A peer Contact Card requires an explicit acceptance record.
- Outcome feedback is private to its owner. It contributes only authoritative
  owner-reported relationship evidence and proposes reviewable Memory.
- Inaccurate-term and safety-concern answers create moderation signals.

## Verification

- Six focused Match lifecycle tests cover participant isolation, public
  projections, calendar generation, dual approval, cancellation, backup,
  Contact Card acceptance, and completion.
- The full local suite passes: 138 Python tests and 7 frontend tests, plus Ruff,
  ESLint, TypeScript, production build, and whitespace validation.
- Candidate-environment and multi-user browser acceptance remain required before
  promotion or `LIVE_VERIFIED` status.
