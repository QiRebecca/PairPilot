"""Owner-scoped Startup V2 Connection read models and provenance."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pairpilot_schemas import ConnectionState

from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.multi_user_platform import (
    PRODUCTION_NAMESPACE,
    SCHEMA_VERSION,
    stable_id,
)
from pairpilot_orchestrator.v2_matches import canonical_match_state


def _clean(document: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if not key.startswith("_")}


async def _owned_connection(
    store: Any, principal: AuthenticatedPrincipal, connection_id: str
) -> dict[str, Any]:
    connection = await store.get("relationships", connection_id)
    if (
        connection is None
        or connection.get("namespace") != PRODUCTION_NAMESPACE
        or connection.get("owner_uid") != principal.uid
    ):
        raise LookupError("connection was not found")
    return connection


async def _peer_identity(store: Any, connection: Mapping[str, Any]) -> dict[str, Any]:
    agent_id = str(connection.get("peer_agent_id") or "")
    agent = await store.get("personal_agents", agent_id) if agent_id else None
    peer_uid = str(
        (agent or {}).get("owner_uid")
        or connection.get("peer_owner_uid_internal")
        or ""
    )
    profile = await store.get("users", peer_uid) if peer_uid else None
    return {
        "peer_uid_internal": peer_uid,
        "person": {
            "display_name": str((profile or {}).get("display_name") or "Connection"),
            "general_location": str((profile or {}).get("general_location") or ""),
        },
        "personal_agent": {
            "agent_id": agent_id,
            "display_name": str((agent or {}).get("display_name") or "Personal Agent"),
        },
    }


async def _connection_controls(
    store: Any, principal: AuthenticatedPrincipal, connection: Mapping[str, Any]
) -> tuple[dict[str, Any], bool]:
    preference_id = stable_id(
        "connection_preference", principal.uid, str(connection.get("relationship_id"))
    )
    preference, blocks = await asyncio.gather(
        store.get("connection_preferences", preference_id),
        store.query_documents(
            "blocks", filters=[("blocker_uid", "EQUAL", principal.uid)]
        ),
    )
    blocked = any(
        item.get("status") == "ACTIVE"
        and item.get("blocked_agent_id") == connection.get("peer_agent_id")
        for item in blocks
    )
    return preference or {}, blocked


def _state(
    connection: Mapping[str, Any], preference: Mapping[str, Any], blocked: bool
) -> ConnectionState:
    if blocked:
        return ConnectionState.BLOCKED
    if preference.get("muted"):
        return ConnectionState.MUTED
    if int(connection.get("successful_plans", 0)) > 0:
        return ConnectionState.ESTABLISHED
    if int(connection.get("plans_committed", 0)) > 0:
        return ConnectionState.COORDINATED
    if connection.get("introduction_path"):
        return ConnectionState.INTRODUCED
    return ConnectionState.DISCOVERED


def _signals(connection: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "dimension": "completed_plans",
            "value": int(connection.get("successful_plans", 0)),
            "evidence": "authoritative owner outcomes",
        },
        {
            "dimension": "response_reliability",
            "value": connection.get("response_reliability", "NOT_ENOUGH_EVIDENCE"),
            "evidence": "stored coordination events only",
        },
        {
            "dimension": "commitment_reliability",
            "value": {
                "plans_committed": int(connection.get("plans_committed", 0)),
                "cancellations": int(connection.get("cancellation_history", 0)),
                "inaccuracy_reports": int(
                    connection.get("commitment_inaccuracy_reports", 0)
                ),
            },
            "evidence": "Match and private owner-outcome events",
        },
        {
            "dimension": "privacy_respect",
            "value": connection.get("privacy_respect", "NOT_ENOUGH_EVIDENCE"),
            "evidence": "no positive claim is inferred from missing reports",
        },
    ]


def _projection(
    connection: Mapping[str, Any],
    identity: Mapping[str, Any],
    preference: Mapping[str, Any],
    blocked: bool,
) -> dict[str, Any]:
    return {
        "connection_id": connection.get("relationship_id"),
        "state": _state(connection, preference, blocked).value,
        "person": identity.get("person"),
        "personal_agent": identity.get("personal_agent"),
        "how_connected": connection.get("relation_type"),
        "introduction_source": connection.get("introduction_path"),
        "shared_community_ids": list(connection.get("relevant_communities") or []),
        "completed_plans": int(connection.get("successful_plans", 0)),
        "plans_committed": int(connection.get("plans_committed", 0)),
        "last_interaction_at": connection.get("last_interaction_at"),
        "task_contexts": list(connection.get("task_type_compatibility") or []),
        "context_signals": _signals(connection),
        "muted": bool(preference.get("muted")),
        "removed_from_suggestions": bool(preference.get("removed_from_suggestions")),
    }


async def list_connections_for_user(
    store: Any, principal: AuthenticatedPrincipal
) -> dict[str, Any]:
    connections = await store.query_documents(
        "relationships", filters=[("owner_uid", "EQUAL", principal.uid)]
    )
    connections = [
        item for item in connections if item.get("namespace") == PRODUCTION_NAMESPACE
    ]
    identities = await asyncio.gather(
        *(_peer_identity(store, connection) for connection in connections)
    )
    controls = await asyncio.gather(
        *(
            _connection_controls(store, principal, connection)
            for connection in connections
        )
    )
    entries = [
        (_projection(connection, identity, preference, blocked), connection)
        for connection, identity, (preference, blocked) in zip(
            connections, identities, controls, strict=True
        )
    ]
    entries.sort(
        key=lambda item: str(item[0].get("last_interaction_at") or ""), reverse=True
    )
    projections = [item[0] for item in entries]
    sources = [item[1] for item in entries]
    recent_cutoff = datetime.now(UTC) - timedelta(days=90)

    def recent(item: Mapping[str, Any]) -> bool:
        value = item.get("last_interaction_at")
        if isinstance(value, datetime):
            timestamp = value if value.tzinfo else value.replace(tzinfo=UTC)
            return timestamp >= recent_cutoff
        return False

    views = {
        "ALL": projections,
        "TRUSTED": [
            item
            for item in projections
            if item["completed_plans"] > 0 and item["state"] not in {"BLOCKED", "MUTED"}
        ],
        "RECENT": [item for item in projections if recent(item)],
        "INTRODUCERS": [
            item
            for item in projections
            if "INTRO" in str(item.get("introduction_source") or "").upper()
        ],
        "COMMUNITIES": [item for item in projections if item["shared_community_ids"]],
        "NEEDS_REVIEW": [
            item
            for item, source in zip(projections, sources, strict=True)
            if int(source.get("cancellation_history", 0)) > 0
            or int(source.get("commitment_inaccuracy_reports", 0)) > 0
        ],
        "BLOCKED": [item for item in projections if item["state"] == "BLOCKED"],
    }
    return {
        "connections": projections,
        "views": views,
        "count": len(projections),
        "graph": {
            "nodes": [
                {"id": "viewer", "label": "You", "kind": "VIEWER"},
                *[
                    {
                        "id": str(item["connection_id"]),
                        "label": str(dict(item["person"] or {}).get("display_name")),
                        "kind": "CONNECTION",
                        "state": item["state"],
                    }
                    for item in projections
                ],
            ],
            "edges": [
                {
                    "source": "viewer",
                    "target": str(item["connection_id"]),
                    "contexts": item["task_contexts"],
                }
                for item in projections
            ],
        },
    }


async def get_connection_detail(
    store: Any, principal: AuthenticatedPrincipal, connection_id: str
) -> dict[str, Any]:
    connection = await _owned_connection(store, principal, connection_id)
    identity = await _peer_identity(store, connection)
    peer_uid = str(identity.pop("peer_uid_internal", ""))
    preference, blocked = await _connection_controls(store, principal, connection)
    matches, rooms, events, usage_events, communities = await asyncio.gather(
        store.query_documents(
            "matches", filters=[("participant_uids", "ARRAY_CONTAINS", principal.uid)]
        ),
        store.query_documents(
            "coordination_rooms",
            filters=[("participant_uids", "ARRAY_CONTAINS", principal.uid)],
        ),
        store.query_documents(
            "relationship_events", filters=[("relationship_id", "EQUAL", connection_id)]
        ),
        store.query_documents(
            "relationship_usage_events",
            filters=[("relationship_id", "EQUAL", connection_id)],
        ),
        asyncio.gather(
            *(
                store.get("communities", str(community_id))
                for community_id in connection.get("relevant_communities", [])
            )
        ),
    )
    shared_matches = [
        item
        for item in matches
        if peer_uid
        and peer_uid in {str(uid) for uid in item.get("participant_uids", [])}
    ]
    shared_rooms = [
        item
        for item in rooms
        if peer_uid
        and peer_uid in {str(uid) for uid in item.get("participant_uids", [])}
    ]
    safe_plans = [
        {
            "match_id": item.get("match_id"),
            "state": canonical_match_state(item).value,
            "title": dict(item.get("terms") or {}).get("title"),
            "terms": dict(item.get("terms") or {}),
            "committed_at": item.get("committed_at"),
            "cancelled_at": item.get("cancelled_at"),
        }
        for item in shared_matches
    ]
    safe_events = [
        {
            key: value
            for key, value in event.items()
            if key
            in {
                "relationship_event_id",
                "match_id",
                "event_type",
                "source",
                "did_plan_happen",
                "would_coordinate_again",
                "agreed_term_inaccurate",
                "either_person_cancelled",
                "created_at",
            }
        }
        for event in events
        if event.get("owner_uid") == principal.uid
    ]
    return {
        "connection": _projection(connection, identity, preference, blocked),
        "shared_communities": [
            {
                key: value
                for key, value in (community or {}).items()
                if key in {"community_id", "name", "location"}
            }
            for community in communities
            if community
        ],
        "plans": safe_plans,
        "active_rooms": [
            {
                "room_id": room.get("room_id"),
                "state": room.get("state") or room.get("status"),
                "room_type": room.get("room_type"),
                "updated_at": room.get("updated_at"),
            }
            for room in shared_rooms
            if str(room.get("status") or room.get("state"))
            not in {"CLOSED", "ARCHIVED"}
        ],
        "relationship_dimensions": _signals(connection),
        "provenance_events": sorted(
            safe_events,
            key=lambda item: str(item.get("created_at") or ""),
            reverse=True,
        ),
        "usage_events": [
            {
                key: value
                for key, value in event.items()
                if key
                in {
                    "usage_id",
                    "task_id",
                    "task_type",
                    "purpose",
                    "context_applicable",
                    "created_at",
                }
            }
            for event in usage_events
            if event.get("owner_uid") == principal.uid
        ],
        "shared_connections": [],
        "safety": {
            "blocked": blocked,
            "private_note": (
                "Shared Connections remain empty unless supported by public or "
                "owner-authorized introduction provenance."
            ),
        },
    }


async def set_connection_preference(
    store: Any,
    principal: AuthenticatedPrincipal,
    *,
    connection_id: str,
    muted: bool | None = None,
    removed_from_suggestions: bool | None = None,
) -> dict[str, Any]:
    await _owned_connection(store, principal, connection_id)
    preference_id = stable_id("connection_preference", principal.uid, connection_id)
    existing = await store.get("connection_preferences", preference_id) or {}
    preference = _clean(existing)
    preference.update(
        schema_version=SCHEMA_VERSION,
        namespace=PRODUCTION_NAMESPACE,
        preference_id=preference_id,
        owner_uid=principal.uid,
        connection_id=connection_id,
        updated_at=datetime.now(UTC),
    )
    if muted is not None:
        preference["muted"] = muted
    if removed_from_suggestions is not None:
        preference["removed_from_suggestions"] = removed_from_suggestions
    await store.upsert("connection_preferences", preference_id, preference)
    return {
        "connection_id": connection_id,
        "muted": bool(preference.get("muted")),
        "removed_from_suggestions": bool(preference.get("removed_from_suggestions")),
    }


async def record_connection_usage(
    store: Any,
    principal: AuthenticatedPrincipal,
    *,
    connection_id: str,
    task_id: str | None,
    purpose: str,
) -> dict[str, Any]:
    connection = await _owned_connection(store, principal, connection_id)
    task = await store.get("task_workspaces", task_id) if task_id else None
    if task_id and (task is None or task.get("owner_uid") != principal.uid):
        raise LookupError("task was not found")
    task_type = str((task or {}).get("task_type") or "")
    supported = {str(item) for item in connection.get("task_type_compatibility", [])}
    applicable = not task_type or not supported or task_type in supported
    usage_id = f"relationship_usage_{uuid4().hex}"
    usage = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "usage_id": usage_id,
        "relationship_id": connection_id,
        "owner_uid": principal.uid,
        "task_id": task_id,
        "task_type": task_type or None,
        "purpose": purpose,
        "context_applicable": applicable,
        "provenance_event_ids": list(connection.get("provenance_event_ids") or []),
        "created_at": datetime.now(UTC),
    }
    await store.create("relationship_usage_events", usage_id, usage)
    return _clean(usage)
