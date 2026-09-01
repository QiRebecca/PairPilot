# Startup V2 Room and channel architecture

Updated: 2026-09-01

## Room workspace

`GET /api/app/rooms` returns only Rooms containing the authenticated user and
groups them as Needs Your Input, Agent Negotiating, Waiting for Peer, Proposal
Ready, Shared Rooms, or Closed. The service maps known legacy states to the
canonical Startup V2 Room state without rewriting production records.

`GET /api/app/rooms/{room_id}` requires active participant authority and returns:

- the associated owner Request and candidate public Post;
- public participant display names and Personal Agent IDs, never login email;
- Room type, state, next actor, autonomy mode, and material update;
- agreed terms, unresolved items, conflicts, uncertainties, current proposal,
  hold status, and next action;
- three separately authorized message collections.

## Three channels

### Private with My Agent

Only messages whose `owner_uid` is the authenticated participant are returned.
The channel may contain sensitive instructions because it is never projected to
the peer participant or their Agent.

### Agents-only negotiation

Both owners may inspect a policy-redacted transcript. Human writes are rejected
by the server. Email, phone, precise room number, and live-location patterns are
redacted defensively from historical Agent messages before owner inspection.

### Shared Human-Agent Room

Read and write are disabled until the Room has become a
`SHARED_COORDINATION_ROOM` with `human_participation_available=true`. Shared
human messages pass the same minimum-necessary disclosure guard in both the V2
channel endpoint and the backward-compatible endpoint.

Every new message records speaker ID and type, authorship, explicit visibility,
provenance, timestamp, and optional reply target. There is no implicit channel
fallback.

## Local verification

Six dedicated tests cover participant isolation, private-channel non-leakage,
Agent-only redaction and human write denial, locked Shared Room denial, shared
contact-detail blocking, V2 list grouping, and owner-scoped mute preferences.
Candidate browser and multi-user acceptance are still required before promotion.
