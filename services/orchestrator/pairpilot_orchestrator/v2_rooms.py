"""Participant-scoped Startup V2 Room read models and channel enforcement."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from pairpilot_schemas import CoordinationRoomState

from pairpilot_orchestrator.auth.authorization import (
    require_room_participant,
    require_verified_email,
)
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.multi_user_platform import (
    PRODUCTION_NAMESPACE,
    SCHEMA_VERSION,
    stable_id,
)
from pairpilot_orchestrator.policies.privacy import OutboundPrivacyGuard
from pairpilot_orchestrator.v2_marketplace import public_post_projection

RoomChannel = Literal["PRIVATE_USER_AGENT", "AGENTS_ONLY", "SHARED_ROOM"]

EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE = re.compile(r"(?<!\w)\+?\d(?:[\s().-]?\d){6,14}(?!\d)")
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
ROOM_NUMBER = re.compile(
    r"\b(?:hotel\s+)?(?:room|suite)\s*(?:number|no\.?|#)?\s*\d{2,6}\b",
    re.IGNORECASE,
)
LIVE_LOCATION = re.compile(
    r"\b(?:right now at|currently at|live location)\b[^.!?]*", re.IGNORECASE
)


def _clean(document: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if not key.startswith("_")}


def _canonical_room_state(room: Mapping[str, Any]) -> CoordinationRoomState:
    explicit = str(room.get("state") or "").upper()
    try:
        return CoordinationRoomState(explicit)
    except ValueError:
        pass
    if (
        room.get("human_participation_available") is True
        or room.get("room_type") == "SHARED_COORDINATION_ROOM"
    ):
        return CoordinationRoomState.SHARED
    status = str(room.get("status") or "").upper()
    if status == "NEEDS_INPUT":
        return CoordinationRoomState.NEEDS_HUMAN_INPUT
    if status in {"COMPLETED", "ARCHIVED"}:
        return CoordinationRoomState.ARCHIVED
    if status == "CLOSED":
        return CoordinationRoomState.CLOSED
    if room.get("proposal_ready") is True:
        return CoordinationRoomState.PROPOSAL_READY
    if room.get("room_type") == "INTRODUCTION_ROOM":
        return CoordinationRoomState.INTRODUCTION
    return CoordinationRoomState.AGENT_NEGOTIATION


def _room_section(room: Mapping[str, Any]) -> str:
    state = _canonical_room_state(room)
    if state == CoordinationRoomState.NEEDS_HUMAN_INPUT:
        return "NEEDS_YOUR_INPUT"
    if state == CoordinationRoomState.PROPOSAL_READY:
        return "PROPOSAL_READY"
    if state == CoordinationRoomState.SHARED:
        return "SHARED_ROOMS"
    if state in {CoordinationRoomState.ARCHIVED, CoordinationRoomState.CLOSED}:
        return "CLOSED"
    if str(room.get("status") or "").upper() == "WAITING_FOR_PEER":
        return "WAITING_FOR_PEER"
    return "AGENT_NEGOTIATING"


def _redact_agent_transcript(content: object) -> tuple[str, bool]:
    original = str(content or "")
    redacted = EMAIL.sub("[contact detail redacted]", original)
    preserved_dates: list[str] = []

    def preserve_date(match: re.Match[str]) -> str:
        preserved_dates.append(match.group(0))
        return f"PAIRPILOTISODATE{len(preserved_dates) - 1}TOKEN"

    redacted = ISO_DATE.sub(preserve_date, redacted)
    redacted = PHONE.sub("[phone redacted]", redacted)
    for index, date in enumerate(preserved_dates):
        redacted = redacted.replace(f"PAIRPILOTISODATE{index}TOKEN", date)
    redacted = ROOM_NUMBER.sub("[precise room redacted]", redacted)
    redacted = LIVE_LOCATION.sub("[live location redacted]", redacted)
    return redacted, redacted != original


def _message_projection(
    message: Mapping[str, Any], *, redact_agents_only: bool = False
) -> dict[str, Any]:
    allowed = {
        "message_id",
        "room_id",
        "task_id",
        "source_intent_id",
        "target_intent_id",
        "speaker_id",
        "speaker_type",
        "authorship",
        "visibility",
        "content",
        "provenance",
        "created_at",
        "reply_to",
    }
    projected = {key: value for key, value in message.items() if key in allowed}
    if redact_agents_only:
        content, was_redacted = _redact_agent_transcript(projected.get("content"))
        projected["content"] = content
        projected["policy_redacted"] = was_redacted
    return projected


def _room_projection(room: Mapping[str, Any]) -> dict[str, Any]:
    state = _canonical_room_state(room)
    allowed = {
        "room_id",
        "proposal_id",
        "community_id",
        "source_task_id",
        "target_task_id",
        "source_intent_id",
        "target_intent_id",
        "participant_agent_ids",
        "room_type",
        "status",
        "human_participation_available",
        "last_material_update",
        "latest_meaningful_event",
        "next_expected_actor",
        "created_at",
        "updated_at",
    }
    projected = {key: value for key, value in room.items() if key in allowed}
    projected.update(state=state.value, section=_room_section(room))
    return projected


async def list_rooms_for_user(
    store: Any, principal: AuthenticatedPrincipal
) -> dict[str, Any]:
    rooms = await store.query_documents(
        "coordination_rooms",
        filters=[("participant_uids", "ARRAY_CONTAINS", principal.uid)],
    )
    visible = [
        _room_projection(room)
        for room in rooms
        if room.get("namespace") == PRODUCTION_NAMESPACE
        and principal.uid not in room.get("revoked_participant_uids", [])
    ]
    visible.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    sections = {
        section: [room for room in visible if room["section"] == section]
        for section in (
            "NEEDS_YOUR_INPUT",
            "AGENT_NEGOTIATING",
            "WAITING_FOR_PEER",
            "PROPOSAL_READY",
            "SHARED_ROOMS",
            "CLOSED",
        )
    }
    return {"rooms": visible, "sections": sections, "count": len(visible)}


async def _participant_cards(
    store: Any, room: Mapping[str, Any], viewer_uid: str
) -> list[dict[str, Any]]:
    uids = [str(uid) for uid in room.get("participant_uids", [])]
    users = await asyncio.gather(*(store.get("users", uid) for uid in uids))
    return [
        {
            "display_name": str((user or {}).get("display_name") or "Participant"),
            "personal_agent_id": str((user or {}).get("personal_agent_id") or ""),
            "is_viewer": uid == viewer_uid,
        }
        for uid, user in zip(uids, users, strict=True)
    ]


async def get_room_workspace(
    store: Any, principal: AuthenticatedPrincipal, room_id: str
) -> dict[str, Any]:
    room = await store.get("coordination_rooms", room_id)
    if room is None or room.get("namespace") != PRODUCTION_NAMESPACE:
        raise LookupError("room was not found")
    require_room_participant(principal, room)
    messages, autonomy, assessments = await asyncio.gather(
        store.query_documents("room_messages", filters=[("room_id", "EQUAL", room_id)]),
        store.get("user_autonomy_configs", principal.uid),
        store.query_documents(
            "candidate_assessments", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
    )
    participant_cards = await _participant_cards(store, room, principal.uid)
    source_task_id = str(room.get("source_task_id") or room.get("task_id") or "")
    target_task_id = str(room.get("target_task_id") or "")
    source_intent_id = str(room.get("source_intent_id") or "")
    target_intent_id = str(room.get("target_intent_id") or "")
    source_task, target_task, source_post, target_post, proposal = await asyncio.gather(
        store.get("task_workspaces", source_task_id)
        if source_task_id
        else asyncio.sleep(0, result=None),
        store.get("task_workspaces", target_task_id)
        if target_task_id
        else asyncio.sleep(0, result=None),
        store.get("intent_posts", source_intent_id)
        if source_intent_id
        else asyncio.sleep(0, result=None),
        store.get("intent_posts", target_intent_id)
        if target_intent_id
        else asyncio.sleep(0, result=None),
        store.get("proposals", str(room.get("proposal_id")))
        if room.get("proposal_id")
        else asyncio.sleep(0, result=None),
    )
    owned_task = (
        source_task
        if (source_task or {}).get("owner_uid") == principal.uid
        else target_task
    )
    candidate_post = (
        target_post
        if (source_post or {}).get("owner_uid") == principal.uid
        else source_post
    )
    assessment = next(
        (
            item
            for item in assessments
            if item.get("room_id") == room_id or item.get("active_room_id") == room_id
        ),
        {},
    )
    channels: dict[str, list[dict[str, Any]]] = {
        "PRIVATE_USER_AGENT": [],
        "AGENTS_ONLY": [],
        "SHARED_ROOM": [],
    }
    for message in sorted(messages, key=lambda item: str(item.get("created_at") or "")):
        visibility = str(message.get("visibility") or "")
        if visibility == "PRIVATE_USER_AGENT":
            if message.get("owner_uid") == principal.uid:
                channels[visibility].append(_message_projection(message))
        elif visibility == "AGENTS_ONLY":
            channels[visibility].append(
                _message_projection(message, redact_agents_only=True)
            )
        elif (
            visibility == "SHARED_ROOM"
            and room.get("human_participation_available") is True
        ):
            channels[visibility].append(_message_projection(message))
    agreed = []
    if proposal and isinstance(proposal.get("terms"), Mapping):
        agreed = [
            {"field": str(key), "value": value}
            for key, value in proposal["terms"].items()
        ]
    state = _canonical_room_state(room)
    next_action = str(room.get("next_action") or "") or (
        "Review the current proposal"
        if state
        in {
            CoordinationRoomState.NEEDS_HUMAN_INPUT,
            CoordinationRoomState.PROPOSAL_READY,
        }
        else "Coordinate in the Shared Room"
        if state == CoordinationRoomState.SHARED
        else "Waiting for the Personal Agents"
    )
    return {
        "room": {
            **_room_projection(room),
            "participants": participant_cards,
            "autonomy_mode": str((autonomy or {}).get("default_mode") or "COPILOT"),
            "associated_request": (
                {
                    key: value
                    for key, value in (owned_task or {}).items()
                    if key in {"task_id", "title", "task_type", "status"}
                }
                if owned_task
                else None
            ),
            "candidate_post": (
                public_post_projection(candidate_post) if candidate_post else None
            ),
        },
        "summary": {
            "agreed": agreed,
            "unresolved": list(assessment.get("uncertainties") or []),
            "conflicts": list(assessment.get("conflicts") or []),
            "uncertainties": list(assessment.get("uncertainties") or []),
            "current_proposal": (
                {
                    "proposal_id": proposal.get("proposal_id"),
                    "version": proposal.get("version"),
                    "status": proposal.get("status"),
                }
                if proposal
                else None
            ),
            "hold_status": str((proposal or {}).get("hold_status") or "NONE"),
            "next_action": next_action,
        },
        "channels": channels,
        "channel_permissions": {
            "PRIVATE_USER_AGENT": {"read": True, "write": True},
            "AGENTS_ONLY": {"read": True, "write": False, "policy_redacted": True},
            "SHARED_ROOM": {
                "read": room.get("human_participation_available") is True,
                "write": room.get("human_participation_available") is True,
            },
        },
    }


async def send_room_channel_message(
    store: Any,
    principal: AuthenticatedPrincipal,
    *,
    room_id: str,
    channel: RoomChannel,
    content: str,
    authorship: str,
    idempotency_key: str,
    reply_to: str | None,
) -> dict[str, Any]:
    require_verified_email(principal)
    room = await store.get("coordination_rooms", room_id)
    if room is None or room.get("namespace") != PRODUCTION_NAMESPACE:
        raise LookupError("room was not found")
    require_room_participant(principal, room)
    if channel == "AGENTS_ONLY":
        raise PermissionError("HUMAN_CANNOT_WRITE_AGENTS_ONLY")
    if channel == "SHARED_ROOM":
        if (
            room.get("room_type") != "SHARED_COORDINATION_ROOM"
            or room.get("human_participation_available") is not True
        ):
            raise PermissionError("SHARED_ROOM_NOT_UNLOCKED")
        OutboundPrivacyGuard().validate(natural_language=content, references=[])
    message_id = stable_id(
        "room_message", room_id, principal.uid, channel, idempotency_key
    )
    message = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "message_id": message_id,
        "room_id": room_id,
        "owner_uid": principal.uid if channel == "PRIVATE_USER_AGENT" else None,
        "speaker_id": principal.uid,
        "speaker_type": "HUMAN",
        "authorship": authorship,
        "visibility": channel,
        "content": content,
        "provenance": {
            "source": "authenticated_room_member",
            "channel_selected_explicitly": True,
        },
        "reply_to": reply_to,
        "created_at": datetime.now(UTC),
    }
    await store.create("room_messages", message_id, message)
    persisted = await store.get("room_messages", message_id)
    return _message_projection(persisted or message)


async def set_room_muted(
    store: Any,
    principal: AuthenticatedPrincipal,
    *,
    room_id: str,
    muted: bool,
) -> dict[str, Any]:
    room = await store.get("coordination_rooms", room_id)
    if room is None or room.get("namespace") != PRODUCTION_NAMESPACE:
        raise LookupError("room was not found")
    require_room_participant(principal, room)
    preference_id = stable_id("room_preference", room_id, principal.uid)
    preference = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "preference_id": preference_id,
        "room_id": room_id,
        "owner_uid": principal.uid,
        "muted": muted,
        "updated_at": datetime.now(UTC),
    }
    await store.upsert("room_preferences", preference_id, preference)
    return _clean(preference)
