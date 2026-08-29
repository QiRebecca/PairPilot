# PairPilot account deletion model

Account deletion is a two-phase safety-preserving workflow.

## Immediate social shutdown

An authenticated user must type `DELETE MY PAIRPILOT ACCOUNT`. The backend then derives the UID from the verified Firebase token and:

1. marks the profile `DELETION_PENDING` and disables discovery;
2. closes all owned public posts;
3. cancels active task workspaces;
4. cancels uncommitted proposals and releases their holds;
5. revokes the user from coordination rooms;
6. creates an owner-scoped deletion request; and
7. revokes Firebase refresh tokens.

The browser cannot supply an `owner_uid` or delete another account.

## Deferred private-data erasure

The deletion request schedules private erasure after a 30-day recovery/operations window. A later administrative worker must delete or anonymize owner-private conversations, intent data, memories, settings and relationships. Minimum safety reports and audit facts may be retained where operationally or legally necessary; they must not remain discoverable social data.

The current beta intentionally does not call Firebase `deleteUser` before the social shutdown succeeds. This prevents an orphaned active social identity.
