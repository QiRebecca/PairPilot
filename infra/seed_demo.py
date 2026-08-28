#!/usr/bin/env python3
"""Idempotently seed world facts only; never seed a workflow trajectory."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import quote

import google.auth
from google.auth.transport.requests import AuthorizedSession

WORKFLOW_COLLECTIONS = (
    "agent_turns",
    "intents",
    "agent_messages",
    "beliefs",
    "proposals",
    "proposal_versions",
    "proposal_acceptances",
    "holds",
    "approval_requests",
    "approvals",
    "matches",
    "runs",
    "run_outputs",
    "events",
    "memories",
    "relationships",
    "relationship_events",
)


def firestore_value(value: Any) -> dict[str, Any]:
    """Encode a bounded Python value as a Firestore REST value."""

    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, datetime):
        timestamp = value.astimezone(UTC).isoformat().replace("+00:00", "Z")
        return {"timestampValue": timestamp}
    if isinstance(value, date):
        return {"stringValue": value.isoformat()}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [firestore_value(item) for item in value]}}
    if isinstance(value, dict):
        return {
            "mapValue": {
                "fields": {
                    str(key): firestore_value(item) for key, item in value.items()
                }
            }
        }
    raise TypeError(f"Unsupported Firestore seed value: {type(value)!r}")


def documents() -> dict[str, dict[str, dict[str, Any]]]:
    """Return deterministic facts and separate private contexts."""

    seeded_at = datetime.now(UTC)
    return {
        "users": {
            "qi-owner": {
                "displayName": "Qi",
                "activeAgentId": "qi-agent",
                "demoOnly": True,
            }
        },
        "agents": {
            "qi-agent": {
                "ownerId": "qi-owner",
                "agentType": "personal_agent",
                "active": True,
                "memoryNamespace": "agent/qi-agent",
            },
            "alice-agent": {
                "ownerId": "alice-owner",
                "agentType": "personal_agent",
                "active": True,
                "memoryNamespace": "agent/alice-agent",
            },
            "maya-agent": {
                "ownerId": "maya-owner",
                "agentType": "personal_agent",
                "active": True,
                "memoryNamespace": "agent/maya-agent",
            },
            "lena-agent": {
                "ownerId": "lena-owner",
                "agentType": "personal_agent",
                "active": True,
                "memoryNamespace": "agent/lena-agent",
            },
        },
        "agent_public_cards": {
            "alice-agent": {
                "agentId": "alice-agent",
                "openToColdContact": False,
                "skills": ["trusted_introduction"],
            },
            "maya-agent": {
                "agentId": "maya-agent",
                "verifiedConferenceAttendee": True,
                "conference": "ICML",
                "gender": "female",
                "availability": {"start": "2026-07-07", "end": "2026-07-10"},
                "overnightRoutineClaim": "quiet",
                "earlyRiser": True,
                "budgetCompatibility": "compatible",
                "openToColdContact": True,
            },
            "lena-agent": {
                "agentId": "lena-agent",
                "verifiedConferenceAttendee": True,
                "conference": "ICML",
                "gender": "female",
                "availability": {"start": "2026-07-06", "end": "2026-07-10"},
                "pricePreference": "lower_cost",
                "overnightRoutineClaim": "regular work calls until about 1:00 AM",
                "openToColdContact": True,
            },
        },
        "agent_private_profiles": {
            "qi-agent": {
                "ownerAgentId": "qi-agent",
                "confirmedPreferences": [
                    "Quiet overnight compatibility matters more than price."
                ],
                "privateFacts": ["The user is a light sleeper."],
                "delegatedAuthority": {"maximumAdditionalCostUsd": 70},
                "commitmentBoundary": "current_proposal_human_approval_required",
                "disclosureBoundary": "minimum_necessary_no_raw_private_fact",
                "readableBy": ["qi-agent"],
            },
            "alice-agent": {
                "ownerAgentId": "alice-agent",
                "knownContacts": ["maya-agent"],
                "introductionAuthority": "alice-decides",
                "readableBy": ["alice-agent"],
            },
            "maya-agent": {
                "ownerAgentId": "maya-agent",
                "decisionAuthority": "maya-decides",
                "readableBy": ["maya-agent"],
            },
            "lena-agent": {
                "ownerAgentId": "lena-agent",
                "decisionAuthority": "lena-decides",
                "readableBy": ["lena-agent"],
            },
        },
        "relationships": {
            "qi-agent__alice-agent__conference-coordination": {
                "sourceAgentId": "qi-agent",
                "targetAgentId": "alice-agent",
                "context": "conference_coordination",
                "relationType": "trusted_prior_connection",
                "coordinationReliability": 0.92,
                "responseReliability": 0.88,
                "privacyRespect": 1.0,
                "successfulPlans": 1,
                "successfulIntroductions": 0,
                "provenanceEventIds": ["seed-prior-dinner-001"],
            }
        },
        "relationship_events": {
            "seed-prior-dinner-001": {
                "eventType": "successful_coordination",
                "context": "conference_dinner",
                "participants": ["qi-agent", "alice-agent"],
                "source": "seeded_world_fact",
                "occurredBeforeDemo": True,
            }
        },
        "availability": {
            "maya-agent": {
                "candidateAgentId": "maya-agent",
                "start": "2026-07-07",
                "end": "2026-07-10",
                "active": True,
                "version": 1,
            },
            "lena-agent": {
                "candidateAgentId": "lena-agent",
                "start": "2026-07-06",
                "end": "2026-07-10",
                "active": True,
                "version": 1,
            },
        },
        "seed_metadata": {
            "pairpilot-demo-v1": {
                "schemaVersion": 1,
                "seededAt": seeded_at,
                "containsWorkflowTrajectory": False,
                "source": "new_hackathon_implementation",
            }
        },
    }


def seed(project_id: str, *, dry_run: bool) -> dict[str, int]:
    """Upsert every deterministic seed document through ADC."""

    data = documents()
    counts = {collection: len(items) for collection, items in data.items()}
    if dry_run:
        return counts

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    session = AuthorizedSession(credentials)
    base = (
        "https://firestore.googleapis.com/v1/projects/"
        f"{project_id}/databases/(default)/documents"
    )
    for collection, items in data.items():
        for document_id, fields in items.items():
            url = f"{base}/{quote(collection)}/{quote(document_id)}"
            response = session.patch(
                url,
                json={
                    "fields": {
                        key: firestore_value(value) for key, value in fields.items()
                    }
                },
                timeout=15,
            )
            response.raise_for_status()
    return counts


def reset_workflow(project_id: str) -> dict[str, int]:
    """Delete only explicitly allowlisted mutable demo collections."""

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    session = AuthorizedSession(credentials)
    base = (
        "https://firestore.googleapis.com/v1/projects/"
        f"{project_id}/databases/(default)/documents"
    )
    deleted: dict[str, int] = {}
    for collection in WORKFLOW_COLLECTIONS:
        count = 0
        while True:
            response = session.get(
                f"{base}/{quote(collection)}",
                params={"pageSize": 100},
                timeout=15,
            )
            response.raise_for_status()
            documents = response.json().get("documents", [])
            if not documents:
                break
            for document in documents:
                delete_response = session.delete(
                    f"https://firestore.googleapis.com/v1/{document['name']}",
                    timeout=15,
                )
                delete_response.raise_for_status()
                count += 1
        deleted[collection] = count
    return deleted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        default=os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
        help="Dedicated Google Cloud project ID",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reset-workflow", action="store_true")
    parser.add_argument(
        "--confirm-project",
        default="",
        help="Required exact project ID when --reset-workflow is used",
    )
    args = parser.parse_args()
    if not args.project:
        parser.error("--project or GOOGLE_CLOUD_PROJECT is required")
    reset_result = None
    if args.reset_workflow:
        if args.dry_run:
            parser.error("--reset-workflow cannot be combined with --dry-run")
        if args.confirm_project != args.project:
            parser.error("--confirm-project must exactly match --project")
        reset_result = reset_workflow(args.project)
    result = seed(args.project, dry_run=args.dry_run)
    print(
        json.dumps(
            {
                "project": args.project,
                "reset": reset_result,
                "documents": result,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
