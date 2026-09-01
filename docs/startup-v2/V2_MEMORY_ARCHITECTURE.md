# Startup V2 Memory architecture

Updated: 2026-09-01

## Authority model

Memory is private, owner-scoped Agent context. It is not a public profile, a
peer-Agent claim store, or an automatically learned global preference.

Canonical types:

- `CONFIRMED_USER_MEMORY`
- `TASK_MEMORY`
- `EPISODIC_MEMORY`
- `RELATIONAL_MEMORY`
- `WORKING_BELIEF`

Legacy Match and outcome types are projected into the canonical vocabulary
without destructively rewriting production records.

## Strict retrieval

`retrieve_memory_context` is the sole V2 Personal Agent retrieval path. It
requires confirmed, enabled, non-archived Memory and enforces:

- global user Memory only in accepted global categories;
- `TASK:<id>` only for that owned task;
- `TASK_TYPE:<type>` and legacy task-type scopes only for that task type;
- `RELATIONSHIP:<id>` only for that Connection;
- episodic Memory never becoming an unrelated global preference;
- working beliefs never becoming durable planning truth;
- `PRIVATE_ONLY`, `DO_NOT_USE`, and historical Match-only Memory exclusion.

A same-topic task exception suppresses the global preference for that task
without overwriting the global record.

## Usage provenance

Every Memory included in a Personal Agent or generic Agent context creates an
owner-scoped `memory_usage_events` record with Memory, task, task type,
relationship, purpose, reason, and timestamp. The detail route uses these exact
events for “Why this was used.”

## Lifecycle and contradiction review

Users can confirm, edit and confirm, reject, restrict scope, temporarily disable,
enable, stop using, archive, and delete. Delete blanks content while retaining
minimum lifecycle audit.

A proposed Memory carrying `contradicts_memory_ids` cannot silently replace a
confirmed Memory. Confirmation leaves it proposed, marks it `NEEDS_REVIEW`, and
creates a high-priority `CONFIRM_MEMORY` Decision.

## Product routes

- `/app/memory` groups Memory into About Me, Preferences, Boundaries, Routines,
  Communication, Task-Specific, Relationships, Waiting for Confirmation,
  Recently Used, and Archived.
- `/app/memory/:memoryId` displays authority, provenance, scope, usage events,
  “Why this was used,” and all lifecycle controls.

## Verification

Five focused V2 tests cover inert proposed/working Memory, scope enforcement,
task exceptions, episodic isolation, usage provenance, contradiction Decisions,
and disable/enable. The complete local gate passes 147 Python tests and 7
frontend tests plus lint, typecheck, build, and diff validation. Candidate
multi-user semantic acceptance remains required before `LIVE_VERIFIED`.
