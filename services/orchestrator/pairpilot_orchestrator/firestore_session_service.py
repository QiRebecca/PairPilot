"""Firestore-backed Google ADK Sessions for persistent user-owned Agents."""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from google.adk.events import Event
from google.adk.sessions import BaseSessionService, Session
from google.adk.sessions.base_session_service import (
    GetSessionConfig,
    ListSessionsResponse,
)

from pairpilot_orchestrator.multi_user_platform import (
    PRODUCTION_NAMESPACE,
    MultiUserStore,
    _clean,
    stable_id,
)


class FirestoreSessionService(BaseSessionService):
    """Persist ADK session state and non-partial events in Firestore."""

    def __init__(self, store: MultiUserStore) -> None:
        self.store = store

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> Session:
        identifier = session_id.strip() if session_id else f"adk_{uuid4().hex}"
        existing = await self.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=identifier,
        )
        if existing is not None:
            return existing
        timestamp = time.time()
        session = Session(
            id=identifier,
            app_name=app_name,
            user_id=user_id,
            state=state or {},
            events=[],
            last_update_time=timestamp,
        )
        created = await self.store.create(
            "adk_sessions",
            identifier,
            {
                "namespace": PRODUCTION_NAMESPACE,
                "session_id": identifier,
                "app_name": app_name,
                "user_id": user_id,
                "state": session.state,
                "last_update_time": timestamp,
                "status": "ACTIVE",
            },
        )
        if not created:
            loaded = await self.get_session(
                app_name=app_name,
                user_id=user_id,
                session_id=identifier,
            )
            if loaded is None:
                raise RuntimeError("ADK session creation conflicted")
            return loaded
        return session

    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: GetSessionConfig | None = None,
    ) -> Session | None:
        document = await self.store.get("adk_sessions", session_id)
        if (
            document is None
            or document.get("status") != "ACTIVE"
            or document.get("app_name") != app_name
            or document.get("user_id") != user_id
        ):
            return None
        event_documents = await self.store.query_documents(
            "adk_session_events",
            filters=[("session_id", "EQUAL", session_id)],
            limit=100,
        )
        events = sorted(
            (
                Event.model_validate(dict(item["event"]))
                for item in event_documents
                if isinstance(item.get("event"), dict)
            ),
            key=lambda event: (event.timestamp, event.id),
        )
        if config is not None:
            if config.after_timestamp is not None:
                events = [
                    event
                    for event in events
                    if event.timestamp >= config.after_timestamp
                ]
            if config.num_recent_events is not None:
                events = (
                    []
                    if config.num_recent_events == 0
                    else events[-config.num_recent_events :]
                )
        return Session(
            id=session_id,
            app_name=app_name,
            user_id=user_id,
            state=dict(document.get("state", {})),
            events=events,
            last_update_time=float(document.get("last_update_time", 0)),
        )

    async def list_sessions(
        self, *, app_name: str, user_id: str | None = None
    ) -> ListSessionsResponse:
        filters: list[tuple[str, str, Any]] = [("app_name", "EQUAL", app_name)]
        if user_id is not None:
            filters.append(("user_id", "EQUAL", user_id))
        documents = await self.store.query_documents(
            "adk_sessions", filters=filters, limit=100
        )
        sessions: list[Session] = []
        for document in documents:
            if document.get("status") != "ACTIVE":
                continue
            session = await self.get_session(
                app_name=app_name,
                user_id=str(document["user_id"]),
                session_id=str(document["session_id"]),
                config=GetSessionConfig(num_recent_events=0),
            )
            if session is not None:
                sessions.append(session)
        return ListSessionsResponse(
            sessions=sorted(sessions, key=lambda item: item.last_update_time)
        )

    async def delete_session(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> None:
        document = await self.store.get("adk_sessions", session_id)
        if (
            document is None
            or document.get("app_name") != app_name
            or document.get("user_id") != user_id
        ):
            return
        clean = _clean(document)
        clean.update(status="DELETED", last_update_time=time.time())
        await self.store.upsert("adk_sessions", session_id, clean)

    async def append_event(self, session: Session, event: Event) -> Event:
        persisted = await super().append_event(session, event)
        if event.partial:
            return persisted
        event_identifier = event.id or stable_id(
            "adk_event",
            session.id,
            event.invocation_id,
            str(event.timestamp),
        )
        await self.store.create(
            "adk_session_events",
            stable_id("adk_session_event", session.id, event_identifier),
            {
                "namespace": PRODUCTION_NAMESPACE,
                "session_id": session.id,
                "user_id": session.user_id,
                "app_name": session.app_name,
                "invocation_id": event.invocation_id,
                "event_id": event_identifier,
                "timestamp": event.timestamp,
                "event": event.model_dump(mode="json"),
            },
        )
        session.last_update_time = max(time.time(), event.timestamp)
        await self.store.upsert(
            "adk_sessions",
            session.id,
            {
                "namespace": PRODUCTION_NAMESPACE,
                "session_id": session.id,
                "app_name": session.app_name,
                "user_id": session.user_id,
                "state": session.state,
                "last_update_time": session.last_update_time,
                "status": "ACTIVE",
            },
        )
        return persisted
