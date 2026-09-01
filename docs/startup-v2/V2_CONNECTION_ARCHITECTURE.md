# Startup V2 Connection architecture

Updated: 2026-09-01

## Product contract

Connections is an owner-scoped view over the existing `relationships` and
`relationship_events` collections. The implementation intentionally avoids a
second competing relationship object. Network Graph remains a secondary view.

## Read models and routes

- `/app/connections` provides All, Trusted, Recent, Introducers, Communities,
  Needs Review, Blocked, and Graph views.
- `/app/connections/:connectionId` is direct-linkable and server-authorized by
  `owner_uid`.
- Cards show the public person and Personal Agent, introduction path, shared
  Community IDs, relevant task contexts, plans, and last interaction.
- Detail shows shared Communities, shared Matches and active Rooms,
  dimension-specific evidence, owner-visible relationship-event provenance,
  and later relationship usage.
- Login email, peer private relationships, peer private notes, and internal peer
  UID are not returned. Shared Connections stays empty unless supported by
  public or owner-authorized introduction provenance.

## Contextual intelligence

No global relationship score is generated. The current dimensions preserve
raw authoritative counts and explicit `NOT_ENOUGH_EVIDENCE` states for response
reliability and privacy respect. Missing reports are not converted into a
positive trust claim.

Relationship reuse is constrained by `task_type_compatibility`. Every explicit
inspection or reuse records an owner-scoped `relationship_usage_events` entry
containing the task, task type, purpose, provenance IDs, and whether the context
was applicable. The Personal Agent warm-introduction tool returns
`CONTEXT_MISMATCH` instead of applying unrelated history.

## Controls

- Mute and removal from suggestions live in a separate owner preference record;
  neither action rewrites authoritative relationship history.
- Block uses the existing cross-surface block invariant, which closes pending
  proposals, releases holds, withdraws candidates, and prevents rediscovery.
- Report uses the existing moderation queue without exposing private content.
- Create-plan and introduction actions seed the persistent Personal Agent
  composer so semantic planning stays with the live Agent.

## Verification

Four focused unit tests cover safe owner projections, detail provenance,
preference separation, and context-scoped usage. The full local test/build gate
must pass before this phase checkpoint. Candidate multi-user acceptance remains
required before `LIVE_VERIFIED`.
