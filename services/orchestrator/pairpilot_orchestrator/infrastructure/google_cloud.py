"""Small typed Firestore REST store with a Pub/Sub outbox."""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from hashlib import sha256
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import google.auth
from google.auth.transport.requests import AuthorizedSession


def encode_value(value: Any) -> dict[str, Any]:
    """Encode bounded application values for the Firestore REST API."""

    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, datetime):
        return {
            "timestampValue": value.astimezone(UTC).isoformat().replace("+00:00", "Z")
        }
    if isinstance(value, date):
        return {"stringValue": value.isoformat()}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [encode_value(item) for item in value]}}
    if isinstance(value, Mapping):
        return {
            "mapValue": {
                "fields": {str(key): encode_value(item) for key, item in value.items()}
            }
        }
    raise TypeError(f"unsupported Firestore value: {type(value)!r}")


def decode_value(value: Mapping[str, Any]) -> Any:
    """Decode the Firestore REST value shapes used by PairPilot."""

    if "nullValue" in value:
        return None
    if "booleanValue" in value:
        return bool(value["booleanValue"])
    if "integerValue" in value:
        return int(value["integerValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "timestampValue" in value:
        return str(value["timestampValue"])
    if "stringValue" in value:
        return str(value["stringValue"])
    if "arrayValue" in value:
        return [decode_value(item) for item in value["arrayValue"].get("values", [])]
    if "mapValue" in value:
        return {
            key: decode_value(item)
            for key, item in value["mapValue"].get("fields", {}).items()
        }
    raise ValueError("unsupported Firestore REST value")


def encode_fields(data: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): encode_value(value) for key, value in data.items()}


def decode_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): decode_value(value) for key, value in fields.items()}


class GoogleCloudStore:
    """Firestore authority boundary and at-least-once Pub/Sub outbox."""

    def __init__(
        self,
        *,
        project_id: str,
        topic_id: str = "pairpilot-events",
        database_id: str = "(default)",
    ) -> None:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self._session = AuthorizedSession(credentials)  # type: ignore[no-untyped-call]
        self.project_id = project_id
        self.topic_id = topic_id
        self._documents = (
            "https://firestore.googleapis.com/v1/projects/"
            f"{project_id}/databases/{database_id}/documents"
        )
        self._topic = (
            "https://pubsub.googleapis.com/v1/projects/"
            f"{project_id}/topics/{topic_id}:publish"
        )

    def _document_url(self, collection: str, document_id: str) -> str:
        return f"{self._documents}/{quote(collection)}/{quote(document_id)}"

    def document_name(self, collection: str, document_id: str) -> str:
        """Return the canonical resource name used in commit writes."""

        return (
            f"projects/{self.project_id}/databases/(default)/documents/"
            f"{collection}/{document_id}"
        )

    async def get(self, collection: str, document_id: str) -> dict[str, Any] | None:
        """Read one authoritative document, returning None for a miss."""

        def read() -> dict[str, Any] | None:
            response = self._session.get(
                self._document_url(collection, document_id), timeout=15
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            body = response.json()
            result = decode_fields(body.get("fields", {}))
            result["_updateTime"] = body.get("updateTime")
            return result

        return await asyncio.to_thread(read)

    async def list_documents(
        self, collection: str, *, max_documents: int = 10_000
    ) -> list[dict[str, Any]]:
        """List a collection with pagination and retain document IDs.

        The explicit cap prevents an accidental unbounded administrative scan.
        Product request paths should continue to use ``query_documents``.
        """

        if not 1 <= max_documents <= 100_000:
            raise ValueError("max_documents must be between 1 and 100000")

        def read() -> list[dict[str, Any]]:
            items: list[dict[str, Any]] = []
            page_token = ""
            while len(items) < max_documents:
                response = self._session.get(
                    f"{self._documents}/{quote(collection)}",
                    params={
                        "pageSize": min(1_000, max_documents - len(items)),
                        **({"pageToken": page_token} if page_token else {}),
                    },
                    timeout=20,
                )
                response.raise_for_status()
                body = response.json()
                for document in body.get("documents", []):
                    item = decode_fields(document.get("fields", {}))
                    item["_id"] = document["name"].rsplit("/", 1)[-1]
                    item["_updateTime"] = document.get("updateTime")
                    items.append(item)
                page_token = str(body.get("nextPageToken", ""))
                if not page_token:
                    break
            return items

        return await asyncio.to_thread(read)

    async def query_documents(
        self,
        collection: str,
        *,
        filters: list[tuple[str, str, Any]],
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Run a bounded server-side query for an authorized projection."""

        if not 1 <= limit <= 100:
            raise ValueError("query limit must be between 1 and 100")
        field_filters = [
            {
                "fieldFilter": {
                    "field": {"fieldPath": field},
                    "op": operator,
                    "value": encode_value(value),
                }
            }
            for field, operator, value in filters
        ]
        where: dict[str, Any] | None
        if len(field_filters) == 1:
            where = field_filters[0]
        elif field_filters:
            where = {
                "compositeFilter": {
                    "op": "AND",
                    "filters": field_filters,
                }
            }
        else:
            where = None

        def read() -> list[dict[str, Any]]:
            query: dict[str, Any] = {
                "from": [{"collectionId": collection}],
                "limit": limit,
            }
            if where is not None:
                query["where"] = where
            response = self._session.post(
                f"{self._documents}:runQuery",
                json={"structuredQuery": query},
                timeout=20,
            )
            response.raise_for_status()
            items = []
            for result in response.json():
                document = result.get("document")
                if document is None:
                    continue
                item = decode_fields(document.get("fields", {}))
                item["_id"] = document["name"].rsplit("/", 1)[-1]
                item["_updateTime"] = document.get("updateTime")
                items.append(item)
            return items

        return await asyncio.to_thread(read)

    async def upsert(
        self, collection: str, document_id: str, data: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Write an application document at a deterministic ID."""

        def write() -> dict[str, Any]:
            response = self._session.patch(
                self._document_url(collection, document_id),
                json={"fields": encode_fields(data)},
                timeout=15,
            )
            response.raise_for_status()
            return decode_fields(response.json().get("fields", {}))

        return await asyncio.to_thread(write)

    async def create(
        self, collection: str, document_id: str, data: Mapping[str, Any]
    ) -> bool:
        """Create exactly once and return False on an existing document."""

        def write() -> bool:
            response = self._session.post(
                f"{self._documents}/{quote(collection)}",
                params={"documentId": document_id},
                json={"fields": encode_fields(data)},
                timeout=15,
            )
            if response.status_code == 409:
                return False
            response.raise_for_status()
            return True

        return await asyncio.to_thread(write)

    async def commit_writes(self, writes: list[dict[str, Any]]) -> dict[str, Any]:
        """Atomically commit preconditioned Firestore writes."""

        def commit() -> dict[str, Any]:
            response = self._session.post(
                f"{self._documents}:commit",
                json={"writes": writes},
                timeout=20,
            )
            response.raise_for_status()
            return dict(response.json())

        return await asyncio.to_thread(commit)

    async def write_event(
        self,
        *,
        event_type: str,
        run_id: str,
        producer: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
        publish_immediately: bool = True,
    ) -> dict[str, Any]:
        """Persist an immutable event and deliver it through the Pub/Sub outbox."""

        event_id = sha256(idempotency_key.encode()).hexdigest()
        event = {
            "eventId": event_id,
            "eventType": event_type,
            "schemaVersion": 1,
            "runId": run_id,
            "producer": producer,
            "payload": dict(payload),
            "idempotencyKey": idempotency_key,
            "createdAt": datetime.now(UTC),
            "published": False,
        }
        created = await self.create("events", event_id, event)
        existing = event if created else await self.get("events", event_id)
        if existing is None:
            raise RuntimeError("event outbox document disappeared")
        if not existing.get("published", False) and publish_immediately:
            message_id = await self._publish(event_id=event_id, event=event)
            event["published"] = True
            event["pubsubMessageId"] = message_id
            await self.upsert("events", event_id, event)
        else:
            message_id = str(existing.get("pubsubMessageId", ""))
        return {
            "event_id": event_id,
            "created": created,
            "published": bool(existing.get("published", False)) or publish_immediately,
            "pubsub_message_id": message_id,
        }

    async def flush_pending_events(self, *, run_id: str) -> int:
        """Publish all durable outbox events for one run after the decision path."""

        flushed = 0
        for event in await self.list_documents("events"):
            if event.get("runId") != run_id or event.get("published") is True:
                continue
            event_id = str(event["eventId"])
            clean_event = {
                key: value for key, value in event.items() if not key.startswith("_")
            }
            message_id = await self._publish(event_id=event_id, event=clean_event)
            clean_event["published"] = True
            clean_event["pubsubMessageId"] = message_id
            await self.upsert("events", event_id, clean_event)
            flushed += 1
        return flushed

    async def _publish(self, *, event_id: str, event: Mapping[str, Any]) -> str:
        safe_event = dict(event)
        safe_event["createdAt"] = (
            safe_event["createdAt"].isoformat()
            if isinstance(safe_event.get("createdAt"), datetime)
            else safe_event.get("createdAt")
        )
        data = base64.b64encode(
            json.dumps(safe_event, sort_keys=True).encode()
        ).decode()

        def publish() -> str:
            response = self._session.post(
                self._topic,
                json={
                    "messages": [
                        {
                            "data": data,
                            "attributes": {
                                "event_id": event_id,
                                "event_type": str(event["eventType"]),
                                "schema_version": "1",
                            },
                        }
                    ]
                },
                timeout=15,
            )
            response.raise_for_status()
            return str(response.json()["messageIds"][0])

        return await asyncio.to_thread(publish)

    async def write_agent_turn(
        self,
        *,
        run_id: str,
        agent_id: str,
        session_id: str,
        model_id: str,
        permitted_context_ids: list[str],
        inbox_message_ids: list[str],
        selected_tool: str,
        redacted_arguments: Mapping[str, Any],
        result: Mapping[str, Any],
        transition: str,
        latency_ms: int,
        retry_count: int = 0,
        token_usage: Mapping[str, Any] | None = None,
        error: str | None = None,
    ) -> str:
        """Persist observable turn metadata without hidden reasoning."""

        turn_id = str(uuid4())
        await self.create(
            "agent_turns",
            turn_id,
            {
                "turnId": turn_id,
                "runId": run_id,
                "agentId": agent_id,
                "sessionId": session_id,
                "modelId": model_id,
                "executionMode": "LIVE GEMINI + GOOGLE ADK + A2A",
                "permittedContextIds": permitted_context_ids,
                "inboxMessageIds": inbox_message_ids,
                "selectedTool": selected_tool,
                "redactedArguments": dict(redacted_arguments),
                "result": dict(result),
                "stateTransition": transition,
                "tokenUsage": dict(token_usage or {}),
                "latencyMs": latency_ms,
                "retryCount": retry_count,
                "error": error,
                "createdAt": datetime.now(UTC),
            },
        )
        return turn_id
