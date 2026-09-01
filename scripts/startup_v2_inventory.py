"""Privacy-safe Startup V2 inventory for Firebase Auth and Firestore.

This script intentionally reports only aggregate counts and collection names. It
never prints emails, user IDs, document contents, tokens, or credentials.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

import firebase_admin
import google.auth
from firebase_admin import auth
from google.auth.transport.requests import AuthorizedSession


def _session() -> AuthorizedSession:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return AuthorizedSession(credentials)


def _collection_ids(session: AuthorizedSession, project_id: str) -> list[str]:
    endpoint = (
        "https://firestore.googleapis.com/v1/projects/"
        f"{project_id}/databases/(default)/documents:listCollectionIds"
    )
    page_token = ""
    result: list[str] = []
    while True:
        body: dict[str, Any] = {"pageSize": 1_000}
        if page_token:
            body["pageToken"] = page_token
        response = session.post(endpoint, json=body, timeout=60)
        response.raise_for_status()
        payload = response.json()
        result.extend(map(str, payload.get("collectionIds", [])))
        page_token = str(payload.get("nextPageToken", ""))
        if not page_token:
            return sorted(set(result))


def _collection_count(
    session: AuthorizedSession, project_id: str, collection_id: str
) -> int:
    endpoint = (
        "https://firestore.googleapis.com/v1/projects/"
        f"{project_id}/databases/(default)/documents:runAggregationQuery"
    )
    body = {
        "structuredAggregationQuery": {
            "structuredQuery": {"from": [{"collectionId": collection_id}]},
            "aggregations": [{"count": {}, "alias": "total"}],
        }
    }
    response = session.post(endpoint, json=body, timeout=60)
    response.raise_for_status()
    payload = response.json()
    for item in payload:
        value = (
            item.get("result", {})
            .get("aggregateFields", {})
            .get("total", {})
            .get("integerValue")
        )
        if value is not None:
            return int(value)
    return 0


def _auth_counts(project_id: str) -> dict[str, int]:
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": project_id})
    total = verified = disabled = controlled = 0
    page = auth.list_users()
    while page:
        for user in page.users:
            total += 1
            verified += int(user.email_verified)
            disabled += int(user.disabled)
            controlled += int("controlled" in (user.display_name or "").casefold())
        page = page.get_next_page()
    return {
        "total": total,
        "email_verified": verified,
        "disabled": disabled,
        "controlled_test_accounts": controlled,
    }


def _identity_platform_summary(
    session: AuthorizedSession, project_id: str
) -> dict[str, Any]:
    endpoint = (
        f"https://identitytoolkit.googleapis.com/admin/v2/projects/{project_id}/config"
    )
    response = session.get(endpoint, timeout=60)
    response.raise_for_status()
    payload = response.json()
    email = payload.get("signIn", {}).get("email", {})
    return {
        "email_enabled": email.get("enabled") is True,
        "password_required": email.get("passwordRequired") is True,
        "mfa_state": payload.get("mfa", {}).get("state", "DISABLED"),
        "authorized_domain_count": len(payload.get("authorizedDomains", [])),
    }


def _monitoring_latest(
    session: AuthorizedSession, project_id: str, metric_type: str
) -> dict[str, float]:
    endpoint = f"https://monitoring.googleapis.com/v3/projects/{project_id}/timeSeries"
    end = datetime.now(UTC)
    params = {
        "filter": f'metric.type="{metric_type}"',
        "interval.startTime": (end - timedelta(hours=1)).isoformat(),
        "interval.endTime": end.isoformat(),
        "view": "FULL",
    }
    response = session.get(endpoint, params=params, timeout=60)
    response.raise_for_status()
    latest: dict[str, float] = {}
    for series in response.json().get("timeSeries", []):
        subscription = str(
            series.get("resource", {}).get("labels", {}).get("subscription_id", "")
        )
        points = series.get("points", [])
        if not subscription or not points:
            continue
        value = points[0].get("value", {})
        raw = value.get("int64Value", value.get("doubleValue", 0))
        latest[subscription] = float(raw)
    return dict(sorted(latest.items()))


def _decode_scalar(value: dict[str, Any]) -> str:
    for key in (
        "stringValue",
        "integerValue",
        "doubleValue",
        "booleanValue",
        "timestampValue",
        "referenceValue",
    ):
        if key in value:
            return str(value[key])
    if "nullValue" in value:
        return "null"
    return "OTHER"


def _field_counts(
    session: AuthorizedSession,
    project_id: str,
    collection_id: str,
    fields: tuple[str, ...],
) -> dict[str, dict[str, int]]:
    endpoint = (
        "https://firestore.googleapis.com/v1/projects/"
        f"{project_id}/databases/(default)/documents:runQuery"
    )
    body = {
        "structuredQuery": {
            "select": {"fields": [{"fieldPath": field} for field in fields]},
            "from": [{"collectionId": collection_id}],
        }
    }
    response = session.post(endpoint, json=body, timeout=60)
    response.raise_for_status()
    counters = {field: Counter() for field in fields}
    for item in response.json():
        document_fields = item.get("document", {}).get("fields", {})
        for field in fields:
            counters[field][_decode_scalar(document_fields.get(field, {}))] += 1
    return {field: dict(sorted(counter.items())) for field, counter in counters.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    session = _session()
    collections = _collection_ids(session, args.project)
    report = {
        "project_id": args.project,
        "firebase_auth": _auth_counts(args.project),
        "identity_platform": _identity_platform_summary(session, args.project),
        "firestore": {
            "collection_count": len(collections),
            "document_counts": {
                collection: _collection_count(session, args.project, collection)
                for collection in collections
            },
            "lifecycle_field_counts": {
                collection: _field_counts(session, args.project, collection, fields)
                for collection, fields in {
                    "candidate_assessments": ("namespace", "state", "priority_band"),
                    "communities": ("namespace", "status", "membership_policy"),
                    "coordination_rooms": ("namespace", "status", "room_type"),
                    "intent_posts": (
                        "namespace",
                        "status",
                        "task_type",
                        "community_id",
                    ),
                    "matches": ("namespace", "status"),
                    "memories": ("namespace", "status", "confirmation_status", "type"),
                    "relationships": ("namespace", "status", "relation_type"),
                    "task_workspaces": ("namespace", "status", "task_type"),
                }.items()
                if collection in collections
            },
        },
        "pubsub_monitoring": {
            "latest_undelivered_messages": _monitoring_latest(
                session,
                args.project,
                "pubsub.googleapis.com/subscription/num_undelivered_messages",
            ),
            "latest_oldest_unacked_seconds": _monitoring_latest(
                session,
                args.project,
                "pubsub.googleapis.com/subscription/oldest_unacked_message_age",
            ),
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
