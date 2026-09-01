"""Versioned, idempotent Startup V2 Firestore migrations.

Migration output is deliberately content-free: reports contain collection names,
counts, and reason codes, never user text or contact information.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Protocol

from pairpilot_orchestrator.infrastructure.google_cloud import encode_fields

V2_SCHEMA_VERSION = 4
PRODUCTION_CONFIRMATION = "APPLY_V2_TO_PRODUCTION"

V2_ENTITY_COLLECTIONS = (
    "users",
    "personal_agents",
    "communities",
    "community_memberships",
    "task_workspaces",
    "conversations",
    "conversation_messages",
    "intent_posts",
    "intent_private_data",
    "saved_posts",
    "saved_searches",
    "candidate_assessments",
    "candidate_rank_events",
    "coordination_rooms",
    "room_participants",
    "room_messages",
    "proposals",
    "proposal_versions",
    "holds",
    "human_approvals",
    "matches",
    "match_participants",
    "contact_cards",
    "relationships",
    "relationship_events",
    "memories",
    "memory_usage_events",
    "decisions",
    "notifications",
    "notification_settings",
    "user_autonomy_configs",
    "blocks",
    "reports",
    "outcomes",
    "agent_invocations",
    "job_failures",
    "usage_quotas",
    "moderation_actions",
    "operator_job_actions",
    "dead_letter_messages",
    "relationship_usage_events",
    "memory_usage_events",
    "audit_events",
)


class MigrationStore(Protocol):
    def document_name(self, collection: str, document_id: str) -> str: ...

    async def get(self, collection: str, document_id: str) -> dict[str, Any] | None: ...

    async def list_documents(
        self, collection: str, *, max_documents: int = 10_000
    ) -> list[dict[str, Any]]: ...

    async def create(
        self, collection: str, document_id: str, data: Mapping[str, Any]
    ) -> bool: ...

    async def commit_writes(self, writes: list[dict[str, Any]]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class MigrationMutation:
    collection: str
    document_id: str
    update_time: str
    replacement: dict[str, Any]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class MigrationPlan:
    migration_id: str
    checksum: str
    environment: str
    scanned: int
    mutations: tuple[MigrationMutation, ...]
    review_required: int
    blocking_count: int
    reason_counts: dict[str, int]

    def public_summary(self) -> dict[str, Any]:
        """Return a privacy-safe summary suitable for logs and reports."""

        collection_counts = Counter(item.collection for item in self.mutations)
        return {
            "migration_id": self.migration_id,
            "checksum": self.checksum,
            "environment": self.environment,
            "scanned": self.scanned,
            "would_mutate": len(self.mutations),
            "review_required": self.review_required,
            "blocking_count": self.blocking_count,
            "collection_counts": dict(sorted(collection_counts.items())),
            "reason_counts": dict(sorted(self.reason_counts.items())),
        }


Transform = Callable[
    [str, Mapping[str, Any], str], tuple[dict[str, Any], tuple[str, ...]]
]


@dataclass(frozen=True)
class MigrationDefinition:
    migration_id: str
    description: str
    collections: tuple[str, ...]
    transform: Transform

    @property
    def checksum(self) -> str:
        material = "|".join(
            (
                self.migration_id,
                self.description,
                *self.collections,
                self.transform.__name__,
            )
        )
        return sha256(material.encode()).hexdigest()


def _clean(document: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if not key.startswith("_")}


def _environment_for(document: Mapping[str, Any]) -> str:
    explicit = str(document.get("environment") or "").strip().lower()
    if explicit in {"production", "candidate", "demo", "local", "test"}:
        return explicit
    namespace = str(document.get("namespace") or "").strip().lower()
    if namespace in {"production", "candidate", "demo", "local", "test"}:
        return namespace
    return "unclassified"


def _v2_001_transform(
    collection: str, document: Mapping[str, Any], target_environment: str
) -> tuple[dict[str, Any], tuple[str, ...]]:
    del collection
    clean = _clean(document)
    reasons: list[str] = []
    source_environment = _environment_for(clean)
    if (
        source_environment != "unclassified"
        and source_environment != target_environment
    ):
        return clean, ("TARGET_ENVIRONMENT_MISMATCH",)
    current_version = clean.get("schema_version", clean.get("schemaVersion"))
    if current_version != V2_SCHEMA_VERSION:
        if "legacy_schema_version" not in clean:
            clean["legacy_schema_version"] = current_version
        clean["schema_version"] = V2_SCHEMA_VERSION
        reasons.append("SCHEMA_VERSION")

    normalized_environment = _environment_for(clean)
    if clean.get("environment") != normalized_environment:
        clean["environment"] = normalized_environment
        reasons.append("ENVIRONMENT_CLASSIFICATION")
    if normalized_environment == "unclassified" and not clean.get(
        "migration_review_required"
    ):
        clean["migration_review_required"] = True
        reasons.append("REVIEW_UNCLASSIFIED_ENVIRONMENT")
    return clean, tuple(reasons)


MIGRATIONS: dict[str, MigrationDefinition] = {
    "V2_001_schema_registry_and_environment": MigrationDefinition(
        migration_id="V2_001_schema_registry_and_environment",
        description="Add V2 schema version and classify record environments",
        collections=V2_ENTITY_COLLECTIONS,
        transform=_v2_001_transform,
    )
}


def _validate_environment(environment: str) -> str:
    normalized = environment.strip().lower()
    if normalized not in {"local", "test", "candidate", "demo", "production"}:
        raise ValueError(
            "environment must be local, test, candidate, demo, or production"
        )
    return normalized


async def plan_migration(
    store: MigrationStore,
    *,
    migration_id: str,
    environment: str,
    max_documents_per_collection: int = 10_000,
) -> MigrationPlan:
    """Scan an explicit environment and produce a non-mutating plan."""

    target_environment = _validate_environment(environment)
    definition = MIGRATIONS[migration_id]
    mutations: list[MigrationMutation] = []
    reason_counts: Counter[str] = Counter()
    scanned = 0
    review_required = 0
    blocking_count = 0
    for collection in definition.collections:
        documents = await store.list_documents(
            collection, max_documents=max_documents_per_collection
        )
        scanned += len(documents)
        for document in documents:
            document_id = str(document.get("_id") or "")
            update_time = str(document.get("_updateTime") or "")
            if not document_id or not update_time:
                raise RuntimeError(
                    f"migration scan for {collection} lacks authoritative metadata"
                )
            replacement, reasons = definition.transform(
                collection, document, target_environment
            )
            if not reasons:
                continue
            reason_counts.update(reasons)
            if "REVIEW_UNCLASSIFIED_ENVIRONMENT" in reasons:
                review_required += 1
            if "TARGET_ENVIRONMENT_MISMATCH" in reasons:
                blocking_count += 1
            mutations.append(
                MigrationMutation(
                    collection=collection,
                    document_id=document_id,
                    update_time=update_time,
                    replacement=replacement,
                    reason_codes=reasons,
                )
            )
    return MigrationPlan(
        migration_id=migration_id,
        checksum=definition.checksum,
        environment=target_environment,
        scanned=scanned,
        mutations=tuple(mutations),
        review_required=review_required,
        blocking_count=blocking_count,
        reason_counts=dict(reason_counts),
    )


def _write_for(store: MigrationStore, mutation: MigrationMutation) -> dict[str, Any]:
    return {
        "update": {
            "name": store.document_name(mutation.collection, mutation.document_id),
            "fields": encode_fields(mutation.replacement),
        },
        "currentDocument": {"updateTime": mutation.update_time},
    }


async def apply_migration(
    store: MigrationStore,
    plan: MigrationPlan,
    *,
    allow_writes: bool = False,
    backup_uri: str | None = None,
    production_confirmation: str | None = None,
) -> dict[str, Any]:
    """Apply a reviewed plan with optimistic concurrency and an audit record."""

    if not allow_writes:
        raise PermissionError("migration writes require allow_writes=True")
    if plan.blocking_count:
        raise PermissionError("migration plan contains environment mismatch blockers")
    if plan.environment == "production" and (
        not backup_uri
        or production_confirmation != PRODUCTION_CONFIRMATION
        or not backup_uri.startswith("gs://")
    ):
        raise PermissionError(
            "production migration requires a GCS backup and exact confirmation"
        )
    registry_id = f"{plan.environment}__{plan.migration_id}"
    existing = await store.get("schema_migrations", registry_id)
    if existing is not None:
        if existing.get("checksum") != plan.checksum:
            raise RuntimeError("applied migration checksum does not match source")
        return {**plan.public_summary(), "applied": False, "already_applied": True}

    for offset in range(0, len(plan.mutations), 400):
        writes = [
            _write_for(store, item) for item in plan.mutations[offset : offset + 400]
        ]
        await store.commit_writes(writes)

    created = await store.create(
        "schema_migrations",
        registry_id,
        {
            "migration_id": plan.migration_id,
            "checksum": plan.checksum,
            "environment": plan.environment,
            "schema_version": V2_SCHEMA_VERSION,
            "mutated_count": len(plan.mutations),
            "review_required_count": plan.review_required,
            "backup_uri": backup_uri,
            "applied_at": datetime.now(UTC),
        },
    )
    if not created:
        raise RuntimeError("migration registry was concurrently created")
    return {**plan.public_summary(), "applied": True, "already_applied": False}


async def run_migration(
    store: MigrationStore,
    *,
    migration_id: str,
    environment: str,
    dry_run: bool = True,
    allow_writes: bool = False,
    backup_uri: str | None = None,
    production_confirmation: str | None = None,
) -> dict[str, Any]:
    """Plan by default; mutation is an explicit, guarded second step."""

    plan = await plan_migration(
        store, migration_id=migration_id, environment=environment
    )
    if dry_run:
        return {**plan.public_summary(), "dry_run": True, "applied": False}
    result = await apply_migration(
        store,
        plan,
        allow_writes=allow_writes,
        backup_uri=backup_uri,
        production_confirmation=production_confirmation,
    )
    return {**result, "dry_run": False}
