# Positive commit verification

Status: **VERIFIED IN PRODUCTION** on 2026-08-29.

## Human action

The real operator entered the request through the composer lifecycle and
clicked **Approve exact effect** in the visible `intent-v2` UI. Automation did
not create the product-evidence approval.

- Run: `47fc6638-e2b5-4253-8b5c-bee46e07278d`
- Proposal/match: `0a8a2e2e-ff84-415a-8d34-a881675215eb`, version 1
- Source intent: `intent_qi_3ca212a9ee004176`
- Target intent: `intent_maya_icml_roommate`
- Pair session: `intent-pair-ee3fcf39f95700117f65`
- Hold: `07e56fbc-ab05-480b-8567-ff994445eccb`
- Human approval: `82b5b3e9-142b-4c9c-a76a-385492ea19d2` at
  `2026-08-29T04:35:08.529958Z`
- Atomic commit: `2026-08-29T04:35:09.258965Z`
- Provenance event: `b4f08e00-d1a4-4029-8f7e-ac05de751078`

The live run reached the boundary in 68.021 seconds after 11 model-selected
tool actions and nine captured token-usage events (27,568 total tokens). It used
Alice's warm introduction, contacted Maya and Lena through intent-scoped A2A,
and proposed the `$62` partial-overlap plan inside the published `$70` limit.

## Atomic effects verified

- Exactly one human approval and one match exist for the proposal.
- Qi and Maya posts both changed to `MATCHED`, capacity `0`, and closed to new
  contacts in the authoritative transaction.
- The Maya pair session changed to `COMMITTED`.
- The competing Lena pair session changed to `RELEASED` with reason
  `conflicting_intent_matched`.
- No active hold remains for the run.
- The OPEN registry returns neither matched post.
- A Qi→Maya `successful_coordination` relationship exists with match/event
  provenance and `introducedThroughAgentId=alice-agent`.
- Qi→Alice `successfulIntroductions` incremented to `1`; the unrelated seeded
  Alice→Maya counter remained unchanged.
- One Qi-owned memory was written as `editable_inference`, scope
  `hotel_sharing`, source `approved_successful_coordination`, confidence 0.78,
  and the same provenance event.
- `match.committed` plus both `intent.matched` records were persisted through
  the durable event/outbox path.
- A production refresh returned run `COMMITTED`, one match, and the Qi post
  still `MATCHED`.

## Duplicate-approval proof

After the human commit, the same exact approved version was replayed once only
to test idempotency. The API returned `status=COMMITTED`, `replayed=true`, and
the original approval/match IDs. Counts before and after were identical:

| Artifact | Before | After |
|---|---:|---:|
| Match for proposal | 1 | 1 |
| Approval for proposal | 1 | 1 |
| Memory for run | 1 | 1 |
| Relationship event for run | 1 | 1 |
| Durable events for run | 27 | 27 |
| Active holds for run | 0 | 0 |
| Qi→Maya relationship for match | 1 | 1 |

This replay did not impersonate a new decision or create a second effect; it
returned the already-authorized committed result.
