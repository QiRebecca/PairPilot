"""Crash-recoverable Firestore leases for asynchronous Agent work."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from pairpilot_orchestrator.multi_user_platform import (
    PRODUCTION_NAMESPACE,
    SCHEMA_VERSION,
    MultiUserStore,
    _clean,
    _create_write,
    _update_write,
    stable_id,
)


def _timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(UTC)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    raise ValueError("lease timestamp is missing")


async def acquire_execution_lease(
    store: MultiUserStore,
    *,
    resource_id: str,
    lease_owner: str,
    duration: timedelta = timedelta(minutes=2),
    now: datetime | None = None,
) -> dict[str, Any] | None:
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    lease_id = stable_id("lease", resource_id)
    existing = await store.get("execution_leases", lease_id)
    if (
        existing is not None
        and existing.get("status") == "ACTIVE"
        and _timestamp(existing.get("expires_at")) > timestamp
    ):
        return None
    version = int(existing.get("lease_version", 0)) + 1 if existing else 1
    lease = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "lease_id": lease_id,
        "resource_id": resource_id,
        "lease_owner": lease_owner,
        "lease_version": version,
        "expires_at": timestamp + duration,
        "attempt": int(existing.get("attempt", 0)) + 1 if existing else 1,
        "status": "ACTIVE",
        "acquired_at": timestamp,
        "updated_at": timestamp,
    }
    write = (
        _create_write(store, "execution_leases", lease_id, lease)
        if existing is None
        else _update_write(
            store,
            "execution_leases",
            lease_id,
            lease,
            update_time=str(existing["_updateTime"]),
        )
    )
    try:
        await store.commit_writes([write])
    except Exception:
        return None
    return lease


async def release_execution_lease(
    store: MultiUserStore,
    lease: dict[str, Any],
    *,
    now: datetime | None = None,
) -> None:
    lease_id = str(lease["lease_id"])
    current = await store.get("execution_leases", lease_id)
    if (
        current is None
        or current.get("lease_owner") != lease.get("lease_owner")
        or current.get("lease_version") != lease.get("lease_version")
    ):
        return
    clean = _clean(current)
    clean.update(
        status="RELEASED",
        released_at=(now or datetime.now(UTC)).astimezone(UTC),
    )
    await store.upsert("execution_leases", lease_id, clean)
