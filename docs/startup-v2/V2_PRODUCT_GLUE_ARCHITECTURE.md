# Startup V2 product glue architecture

Updated: 2026-09-01

## Decision Inbox

`/app/decisions` is an owner-scoped aggregation over existing Decisions. It
normalizes legacy types, exposes only authoritative entity routes, and separates
Open from Resolved. Version-bound proposal, Match-change, and eligible Memory
decisions can resolve inline; other decisions route to their authoritative
workflow rather than simulating success.

Rejecting a Match change resolves the owner Decision and rejects that version.
Approval delegates to the existing atomic proposal commit or exact-version Match
change service. Cross-owner resolution is denied.

## Notifications

`/app/notifications` projects owner notifications into seven meaningful
categories and maps authorized entity IDs to product routes. It supports
read/unread, mark all read, archive, filtering, quiet hours, and preferences.

Browser push remains honestly disabled unless an explicit registered consent
token exists. This phase does not claim fake push or email delivery.

## Autonomy Center

`/app/settings/autonomy` replaces the vague Full Access control with twelve
actions, each set to `AUTOMATIC`, `ASK_FIRST`, or `NEVER`. It supports global
defaults, owned task overrides, and an owner-visible policy activity history.

Infrastructure forces `APPROVE_FINAL_COMMITMENT` to `ASK_FIRST`; it cannot be
saved as automatic. Protected information defaults to `NEVER`. The live
Personal Agent Post publishing tool now consults the action-specific
`PUBLISH_POST` policy instead of the legacy mode switch. Other action paths must
be migrated to the common helper before the Autonomy Center can leave PARTIAL.

## Presentation directives

The directive allowlist now covers the Startup V2 product vocabulary, including
Post Detail, Candidate Pool, Rooms, Match, Connection, Memory, Community, and
Explore. Before persistence, every model-supplied entity ID is checked against
owner, participant, or public authority. The frontend renders only known typed
cards and then opens a route that fetches authoritative data.

## Verification

Five product-glue tests cover Decision ownership/routing/rejection,
Notification state and route isolation, honest push settings, global/task
Autonomy behavior, locked commitment, and unauthorized directive rejection.
The complete local gate passes 152 Python tests and 7 frontend tests plus lint,
typecheck, build, and diff validation.

Candidate multi-user browser acceptance, browser-push registration, remaining
inline Decision handlers, and runtime enforcement for all autonomy actions are
still required.
