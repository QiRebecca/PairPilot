from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from pairpilot_orchestrator.infrastructure.google_cloud import decode_fields
from pairpilot_orchestrator.startup_v2_migrations import (
    PRODUCTION_CONFIRMATION,
    apply_migration,
    plan_migration,
    run_migration,
)

MIGRATION_ID = "V2_001_schema_registry_and_environment"
CONVERGENCE_MIGRATION_ID = "V2_002_runtime_metadata_convergence"


class MigrationMemoryStore:
    def __init__(self) -> None:
        self.collections: defaultdict[str, dict[str, dict[str, Any]]] = defaultdict(
            dict
        )
        self.version = 0

    def _stamp(self, value: Mapping[str, Any]) -> dict[str, Any]:
        self.version += 1
        return {**dict(value), "_updateTime": f"version-{self.version}"}

    def document_name(self, collection: str, document_id: str) -> str:
        return f"projects/test/databases/(default)/documents/{collection}/{document_id}"

    async def get(self, collection: str, document_id: str) -> dict[str, Any] | None:
        value = self.collections[collection].get(document_id)
        return dict(value) if value is not None else None

    async def list_documents(
        self, collection: str, *, max_documents: int = 10_000
    ) -> list[dict[str, Any]]:
        return [
            {**dict(value), "_id": document_id}
            for document_id, value in list(self.collections[collection].items())[
                :max_documents
            ]
        ]

    async def create(
        self, collection: str, document_id: str, data: Mapping[str, Any]
    ) -> bool:
        if document_id in self.collections[collection]:
            return False
        self.collections[collection][document_id] = self._stamp(data)
        return True

    async def commit_writes(self, writes: list[dict[str, Any]]) -> dict[str, Any]:
        for write in writes:
            update = write["update"]
            collection, document_id = (
                str(update["name"]).split("/documents/", 1)[1].split("/", 1)
            )
            current = self.collections[collection][document_id]
            assert current["_updateTime"] == write["currentDocument"]["updateTime"]
            self.collections[collection][document_id] = self._stamp(
                decode_fields(update["fields"])
            )
        return {"writeResults": len(writes)}


@pytest.mark.asyncio
async def test_dry_run_is_content_free_and_does_not_write() -> None:
    store = MigrationMemoryStore()
    await store.create(
        "intent_posts",
        "post-a",
        {
            "schema_version": 3,
            "namespace": "candidate",
            "public_summary": "private-like test marker must never enter report",
        },
    )
    result = await run_migration(
        store,
        migration_id=MIGRATION_ID,
        environment="candidate",
    )
    assert result["dry_run"] is True
    assert result["would_mutate"] == 1
    assert "private-like" not in str(result)
    assert store.collections["intent_posts"]["post-a"]["schema_version"] == 3


@pytest.mark.asyncio
async def test_candidate_apply_is_idempotent() -> None:
    store = MigrationMemoryStore()
    await store.create(
        "matches", "match-a", {"schema_version": 3, "namespace": "candidate"}
    )
    plan = await plan_migration(
        store, migration_id=MIGRATION_ID, environment="candidate"
    )
    first = await apply_migration(store, plan, allow_writes=True)
    assert first["applied"] is True
    assert store.collections["matches"]["match-a"]["schema_version"] == 4

    converged_plan = await plan_migration(
        store, migration_id=MIGRATION_ID, environment="candidate"
    )
    assert converged_plan.mutations == ()
    second = await apply_migration(store, converged_plan, allow_writes=True)
    assert second["already_applied"] is True


@pytest.mark.asyncio
async def test_applied_migration_fails_loudly_when_new_drift_appears() -> None:
    store = MigrationMemoryStore()
    await store.create(
        "matches", "match-a", {"schema_version": 3, "namespace": "candidate"}
    )
    first_plan = await plan_migration(
        store, migration_id=MIGRATION_ID, environment="candidate"
    )
    await apply_migration(store, first_plan, allow_writes=True)
    await store.create(
        "matches", "match-b", {"schema_version": 3, "namespace": "candidate"}
    )
    drifted_plan = await plan_migration(
        store, migration_id=MIGRATION_ID, environment="candidate"
    )
    with pytest.raises(RuntimeError, match="new drift"):
        await apply_migration(store, drifted_plan, allow_writes=True)


@pytest.mark.asyncio
async def test_v2_002_converges_records_created_after_v2_001() -> None:
    store = MigrationMemoryStore()
    await store.create(
        "matches", "match-a", {"schema_version": 3, "namespace": "candidate"}
    )
    first_plan = await plan_migration(
        store, migration_id=MIGRATION_ID, environment="candidate"
    )
    await apply_migration(store, first_plan, allow_writes=True)
    await store.create(
        "intent_posts",
        "post-after-v2-001",
        {"schema_version": 3, "namespace": "candidate"},
    )

    convergence_plan = await plan_migration(
        store,
        migration_id=CONVERGENCE_MIGRATION_ID,
        environment="candidate",
    )
    assert len(convergence_plan.mutations) == 1
    result = await apply_migration(store, convergence_plan, allow_writes=True)
    assert result["applied"] is True
    converged = store.collections["intent_posts"]["post-after-v2-001"]
    assert converged["schema_version"] == 4
    assert converged["environment"] == "candidate"

    final_plan = await plan_migration(
        store,
        migration_id=CONVERGENCE_MIGRATION_ID,
        environment="candidate",
    )
    assert final_plan.mutations == ()
    second = await apply_migration(store, final_plan, allow_writes=True)
    assert second["already_applied"] is True


@pytest.mark.asyncio
async def test_environment_mismatch_blocks_writes() -> None:
    store = MigrationMemoryStore()
    await store.create(
        "users", "user-a", {"schema_version": 3, "namespace": "production"}
    )
    plan = await plan_migration(
        store, migration_id=MIGRATION_ID, environment="candidate"
    )
    assert plan.blocking_count == 1
    with pytest.raises(PermissionError, match="environment mismatch"):
        await apply_migration(store, plan, allow_writes=True)


@pytest.mark.asyncio
async def test_production_apply_requires_backup_and_exact_confirmation() -> None:
    store = MigrationMemoryStore()
    await store.create(
        "users", "user-a", {"schema_version": 3, "namespace": "production"}
    )
    plan = await plan_migration(
        store, migration_id=MIGRATION_ID, environment="production"
    )
    with pytest.raises(PermissionError, match="GCS backup"):
        await apply_migration(store, plan, allow_writes=True)
    result = await apply_migration(
        store,
        plan,
        allow_writes=True,
        backup_uri="gs://pairpilot-backups/export-001",
        production_confirmation=PRODUCTION_CONFIRMATION,
    )
    assert result["applied"] is True
    record = store.collections["schema_migrations"][f"production__{MIGRATION_ID}"]
    assert isinstance(record["applied_at"], datetime)
    assert record["applied_at"].tzinfo == UTC
