# Startup V2 data migration report

Updated: 2026-09-01

## Current result

Only a read-only production dry-run has been performed. No Startup V2 migration
has been applied to candidate or production data.

```text
Migration: V2_001_schema_registry_and_environment
Project: pairpilot-agentic-ecb84a
Environment: production
Mode: dry-run
Documents scanned: 3,093
Documents written: 0
Environment mismatch blockers: 0
Records requiring environment review: 26
Potential schema/environment metadata updates: 3,093
Checksum: 26db6fdbb922519d07645558c70c1618f42b654fe92f2ec63883c5f052214f8d
```

The report intentionally contains no document IDs, user IDs, email addresses,
post text, message text, contact fields, tokens, or credentials.

## What was verified

- The runner defaults to dry-run and requires an explicit environment.
- Firestore pagination scans beyond the previous 100-document first page.
- A candidate run refuses to apply over production-labelled documents.
- Production apply requires all three controls: an explicit write flag, a
  `gs://` backup/export URI, and the exact production confirmation phrase.
- Writes use Firestore update-time preconditions and batches of at most 400.
- An applied migration is recorded by environment, ID, and checksum; replay is
  idempotent and a changed checksum fails closed.
- Public output contains aggregate counts and reason codes only.

## Findings

Twenty-six historical records have neither a recognized `environment` nor a
recognized `namespace`. The migration classifies these as `unclassified` and
marks them for review; it does not silently treat them as production or demo
data.

The first migration would also preserve the prior schema version before adding
the V2 schema version. It does not delete or rename historical fields.

## Automated evidence

```text
Python: 115 passed
Frontend: 7 passed
Ruff: passed
ESLint: passed
TypeScript: passed
Production build: passed
git diff --check: passed
```

## Gates still required before apply

1. Create a dedicated encrypted Firestore export bucket in the selected region
   with retention and access controls.
2. Create an isolated candidate data environment and candidate Pub/Sub route.
3. Review and classify the 26 unclassified records without exposing their
   contents in logs.
4. Run the migration against candidate, then run it a second time and prove zero
   additional mutations.
5. Complete candidate security, multi-user, lifecycle, and visual acceptance.
6. Obtain an explicit production promotion decision.

## Rollback / forward-fix

Application rollback remains the preserved Cloud Run revision. Migration writes
are additive and preserve legacy values. If a later applied migration is faulty,
route traffic back to the preserved revision and use a reviewed forward-fix;
restore the Firestore export only for catastrophic corruption.
