# Startup V2 Community architecture

Updated: 2026-09-01

## Operational boundary

Communities are server-authorized marketplace containers, not decorative tags.
The canonical membership types are `PUBLIC`, `INVITE_LINK`,
`APPROVAL_REQUIRED`, `DOMAIN_VERIFIED`, and `PRIVATE`. Roles are derived from an
active server-side membership record; the client cannot grant itself moderator
or administrator authority.

## Read model

`GET /api/app/communities/{community_id}` returns one bounded projection:

- public Community purpose, dates, general location, membership type, and rules;
- aggregate counts;
- public Post projections grouped by supported request type, only for members;
- public member and Personal Agent cards, only for members;
- Rooms explicitly visible to the Community or already containing the viewer;
- no login email, precise location, private profile, Memory, private task data,
  message body, or Agents-only negotiation transcript.

Explicitly labelled controlled-demo/test identities and Posts are excluded from
real user discovery. The implementation does not infer test identity from user
behavior or naming that lacks an explicit marker.

## Community Agent

Each Community has a logical identity `community_agent:{community_id}`. Its
query surface is intentionally deterministic and uses only the same safe read
model as the Community UI. It can explain rules and surface public Posts. It
cannot read protected Memory, private task transcripts, private membership data,
or Agents-only negotiation, and it cannot approve a Match or impersonate a
moderator.

## Local acceptance evidence

The authenticated browser acceptance run verified:

- Community list to direct Community Detail navigation;
- Overview, Open Requests, Members & Agents, Plans & Rooms, and Rules tabs;
- explicit empty state when no open Post exists;
- controlled test identities excluded from the member directory;
- a Community Agent rules query completing successfully;
- no application console errors.

The acceptance run was read-only against production data except for the
non-persistent Community Agent query. Join, leave, moderation, and candidate
environment behavior remain gated for later acceptance.
