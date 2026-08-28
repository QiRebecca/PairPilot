"""Provenance records for remote peer-agent exchanges."""

import asyncio
from datetime import datetime, timezone
from hashlib import sha256
from typing import Protocol

import google.auth
from google.auth.transport.requests import AuthorizedSession
from pydantic import BaseModel, ConfigDict, Field


class A2AProvenanceRecord(BaseModel):
    """Observable evidence that a response came through a remote agent boundary."""

    model_config = ConfigDict(extra="forbid")

    inbound_message_id: str
    outbound_message_id: str
    from_agent_id: str
    to_agent_id: str
    protocol: str = "A2A/JSON-RPC/1.0"
    exact_model_id: str
    response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class ProvenanceStore(Protocol):
    """Persistence boundary shared by local tests and Cloud Run."""

    async def persist(
        self,
        *,
        inbound_message_id: str,
        outbound_message_id: str,
        response_text: str,
        model_id: str,
    ) -> A2AProvenanceRecord:
        """Persist one immutable provenance record."""


def build_record(
    *,
    inbound_message_id: str,
    outbound_message_id: str,
    response_text: str,
    model_id: str,
) -> A2AProvenanceRecord:
    """Build the canonical record before choosing a storage adapter."""

    return A2AProvenanceRecord(
        inbound_message_id=inbound_message_id,
        outbound_message_id=outbound_message_id,
        from_agent_id="alice-agent",
        to_agent_id="qi-agent",
        exact_model_id=model_id,
        response_sha256=sha256(response_text.encode()).hexdigest(),
    )


class InMemoryProvenanceStore:
    """Bounded spike store; production replaces this with Firestore."""

    def __init__(self) -> None:
        self.records: list[A2AProvenanceRecord] = []

    async def persist(
        self,
        *,
        inbound_message_id: str,
        outbound_message_id: str,
        response_text: str,
        model_id: str,
    ) -> A2AProvenanceRecord:
        """Persist one immutable local record for spike verification."""

        record = build_record(
            inbound_message_id=inbound_message_id,
            outbound_message_id=outbound_message_id,
            response_text=response_text,
            model_id=model_id,
        )
        self.records.append(record)
        return record


class FirestoreProvenanceStore:
    """Persist immutable A2A evidence through the official Firestore REST API."""

    def __init__(self, *, project_id: str, database_id: str = "(default)") -> None:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self._session = AuthorizedSession(credentials)
        self._collection_url = (
            "https://firestore.googleapis.com/v1/projects/"
            f"{project_id}/databases/{database_id}/documents/"
            "a2a_spike_provenance"
        )

    async def persist(
        self,
        *,
        inbound_message_id: str,
        outbound_message_id: str,
        response_text: str,
        model_id: str,
    ) -> A2AProvenanceRecord:
        """Create a unique Firestore document and fail closed on errors."""

        record = build_record(
            inbound_message_id=inbound_message_id,
            outbound_message_id=outbound_message_id,
            response_text=response_text,
            model_id=model_id,
        )
        payload = {
            "fields": {
                "inboundMessageId": {"stringValue": record.inbound_message_id},
                "outboundMessageId": {"stringValue": record.outbound_message_id},
                "fromAgentId": {"stringValue": record.from_agent_id},
                "toAgentId": {"stringValue": record.to_agent_id},
                "protocol": {"stringValue": record.protocol},
                "exactModelId": {"stringValue": record.exact_model_id},
                "responseSha256": {"stringValue": record.response_sha256},
                "createdAt": {
                    "timestampValue": record.created_at.isoformat().replace(
                        "+00:00", "Z"
                    )
                },
            }
        }

        def write() -> None:
            response = self._session.post(
                self._collection_url,
                params={"documentId": record.outbound_message_id},
                json=payload,
                timeout=10,
            )
            response.raise_for_status()

        await asyncio.to_thread(write)
        return record
