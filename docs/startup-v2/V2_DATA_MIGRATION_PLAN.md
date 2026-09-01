# Startup V2 data migration plan

Updated: 2026-09-01

## Principles

1. Never mutate production first.
2. Export Firestore before the first production migration.
3. Every migration has an ID, checksum, dry-run output, applied timestamp, and
   idempotency test.
4. Migrations operate on an explicit environment and namespace.
5. Existing public/private separation remains authoritative.
6. Unknown legacy values are classified, not silently guessed.
7. Historical records are preserved; forward-fix is preferred after promotion.

## Collection mapping

| V2 meaning | Existing authoritative collection | Action |
|---|---|---|
| public Intent Posts | `intent_posts` | retain; add V2 fields and indexes |
| private Intent data | `intent_private_data` | retain; never expose through public APIs |
| Connections | `relationships` + `relationship_events` | retain storage; expose V2 Connections terminology |
| notification preferences | `notification_settings` | retain and extend |
| autonomy policies | `user_autonomy_configs` | retain and migrate to action policies |
| contact offers | `contact_cards` | retain; add offer/accept/revoke metadata |
| outcome feedback | `outcomes` | retain; add relationship-event linkage |
| Agent runs | `agent_invocations` + `job_failures` | retain; add privacy-safe operational projection |

New collections will be introduced only for genuinely new meanings:

```text
schema_migrations
saved_posts
saved_searches
saved_search_runs
memory_usage_events
contact_profiles
contact_offers (only if existing contact_cards cannot safely carry offer history)
connections_projection (only if query needs require it)
moderation_actions
audit_events_v2
product_analytics_daily
```

## Planned migrations

### `V2_001_schema_registry_and_environment`

- create migration registry and environment metadata;
- add `schema_version` and normalized `environment` where absent;
- classify unnamespaced documents without changing visibility;
- no lifecycle state changes.

### `V2_002_intent_and_task_normalization`

- map `conference_room_share` to `ROOM_SHARE`;
- map `peer_coordination` only from authoritative event/goal evidence; ambiguous
  records are marked `migration_review_required`;
- add Post lifecycle metadata and status transition version;
- preserve every legacy value in `legacy_state`.

### `V2_003_rooms_proposals_matches`

- normalize Room types and states;
- materialize missing proposal version history from immutable approvals where
  provable;
- add Match lifecycle state without claiming an event happened;
- flag inconsistent approval/hold combinations for review.

### `V2_004_connections_and_memory`

- normalize Relationship documents into Connection semantics;
- add context-specific relationship dimensions derived only from relationship
  events;
- normalize Memory state/type/scope/provenance;
- keep unconfirmed Memory inert.

### `V2_005_decisions_notifications_autonomy`

- normalize decision types and entity links;
- add notification read/category/deep-link fields;
- expand coarse autonomy modes into per-action policies with conservative defaults;
- final commitment remains `ASK_FIRST` and cannot be migrated to automatic.

### `V2_006_demo_namespace_separation`

- identify fixed hackathon identities from explicit seed metadata and controlled
  account labels;
- move only synthetic marketplace visibility into the demo namespace;
- never infer that an unlabeled account is synthetic;
- preserve Auth accounts unless the owner separately authorizes deletion.

## Execution workflow

1. Create an encrypted Firestore export in a project-owned GCS bucket.
2. Record export URI, database update time, source revision, and image digest.
3. Run migration in `--dry-run --environment candidate` mode.
4. Store counts and proposed changes without document content.
5. Apply to the candidate namespace.
6. Run idempotency twice; the second apply must produce zero mutations.
7. Run security, lifecycle, and multi-user acceptance.
8. Produce `V2_DATA_MIGRATION_REPORT.md`.
9. Apply to production only after an explicit promotion gate.

## Rollback and forward-fix

- Application rollback uses preserved Cloud Run revisions.
- Migration writes preserve `legacy_state`, `legacy_schema_version`, and migration ID.
- Destructive field removal is prohibited in V2 migrations.
- If a production issue is discovered after migration, route application traffic
  back and apply a reviewed forward-fix; restore the export only for catastrophic
  corruption.

## Current blockers

- No dedicated europe-west2 export bucket or retention policy exists; the US
  Cloud Build source bucket must not be reused for database backups.
- No candidate collection namespace exists for migration acceptance.
- Two candidate assessments, two Rooms, two Relationships, and one Task require
  namespace classification.
- Match and Relationship status mappings need domain rules before code is written.
