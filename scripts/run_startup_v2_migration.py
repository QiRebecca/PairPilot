#!/usr/bin/env python3
"""Run a privacy-safe Startup V2 migration plan; dry-run is the default."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_IDS = (
    "V2_001_schema_registry_and_environment",
    "V2_002_runtime_metadata_convergence",
)
PRODUCTION_CONFIRMATION = "APPLY_V2_TO_PRODUCTION"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "migration_id", choices=MIGRATION_IDS, help="versioned migration ID"
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=("local", "test", "candidate", "demo", "production"),
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
        help="Google Cloud project (or GOOGLE_CLOUD_PROJECT)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="apply the reviewed plan; without this flag the command is read-only",
    )
    parser.add_argument(
        "--collection-prefix",
        default="",
        help="required for non-production environments (for example candidate_v2_)",
    )
    parser.add_argument("--backup-uri", help="required GCS export URI for production")
    parser.add_argument(
        "--production-confirmation",
        help=f"production only; exact value: {PRODUCTION_CONFIRMATION}",
    )
    args = parser.parse_args()
    if not args.project:
        parser.error("--project or GOOGLE_CLOUD_PROJECT is required")
    if args.environment != "production" and not args.collection_prefix:
        parser.error("--collection-prefix is required outside production")
    if args.environment == "production" and args.collection_prefix:
        parser.error("production migrations cannot use a collection prefix")
    return args


async def main() -> None:
    args = parse_args()
    sys.path[:0] = [
        str(REPOSITORY_ROOT / "services" / "orchestrator"),
        str(REPOSITORY_ROOT / "packages" / "schemas"),
    ]
    from pairpilot_orchestrator.infrastructure.google_cloud import GoogleCloudStore
    from pairpilot_orchestrator.startup_v2_migrations import run_migration

    store = GoogleCloudStore(
        project_id=args.project,
        collection_prefix=args.collection_prefix,
        environment=args.environment,
    )
    result = await run_migration(
        store,
        migration_id=args.migration_id,
        environment=args.environment,
        dry_run=not args.apply,
        allow_writes=args.apply,
        backup_uri=args.backup_uri,
        production_confirmation=args.production_confirmation,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
