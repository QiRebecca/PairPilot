"""Run additional live Startup V2 lifecycle gates against the isolated candidate."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    REPO_ROOT / "packages" / "schemas",
    REPO_ROOT / "services" / "orchestrator",
    REPO_ROOT / "services" / "peer_agents",
    REPO_ROOT / "scripts",
):
    sys.path.insert(0, str(source_root))

import requests  # noqa: E402
from run_startup_v2_candidate_acceptance import (  # noqa: E402
    BASE_URL,
    ControlledUser,
    _admin_session,
    _api,
    _approve_plan,
    _assert_candidate_target,
    _contact_pairs,
    _firebase_api_key,
    _states,
    _users,
)

Pair = tuple[ControlledUser, dict[str, Any], ControlledUser, dict[str, Any]]


def _raw(
    user: ControlledUser,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> requests.Response:
    return requests.request(
        method,
        BASE_URL + path,
        headers={
            "Authorization": f"Bearer {user.token}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=90,
    )


def _expect_status(
    user: ControlledUser,
    method: str,
    path: str,
    status: int,
    body: dict[str, Any] | None = None,
) -> None:
    response = _raw(user, method, path, body)
    if response.status_code != status:
        raise RuntimeError(
            f"expected HTTP {status} for {method} {path}; got "
            f"{response.status_code}: {response.text[:500]}"
        )


def _open_pair(
    users: list[ControlledUser], states: dict[int, dict[str, Any]]
) -> Pair:
    grouped: dict[
        tuple[str, str], list[tuple[ControlledUser, dict[str, Any]]]
    ] = {}
    for user in users:
        state = states[user.index]
        posts_by_task = {
            str(post.get("task_id")): post
            for post in state["myPosts"]
            if post.get("status") == "OPEN"
        }
        for task in state["tasks"]:
            post = posts_by_task.get(str(task["task_id"]))
            if post is None:
                continue
            key = (str(task["task_type"]), str(task["community_id"]))
            grouped.setdefault(key, []).append((user, {**task, **post}))
    for candidates in grouped.values():
        if len(candidates) < 2:
            continue
        owner, own = candidates[0]
        peer, peer_post = next(
            item for item in candidates[1:] if item[0].uid != owner.uid
        )
        return owner, own, peer, peer_post
    raise RuntimeError("no uncommitted compatible candidate pair remains")


def _active_context(
    users: list[ControlledUser], states: dict[int, dict[str, Any]]
) -> tuple[Pair, dict[str, Any], str] | None:
    for owner in users:
        owner_state = states[owner.index]
        for match in owner_state["matches"]:
            if str(match.get("status") or "") != "COMMITTED":
                continue
            match_id = str(match["match_id"])
            peer = next(
                (
                    user
                    for user in users
                    if user.uid != owner.uid
                    and any(
                        item.get("match_id") == match_id
                        for item in states[user.index]["matches"]
                    )
                ),
                None,
            )
            if peer is None:
                continue
            intent_ids = {
                str(match.get("source_intent_id") or ""),
                str(match.get("target_intent_id") or ""),
            }
            own = next(
                (
                    {**task, **post}
                    for task in owner_state["tasks"]
                    for post in owner_state["myPosts"]
                    if task.get("intent_id") in intent_ids
                    and post.get("intent_id") == task.get("intent_id")
                ),
                None,
            )
            peer_post = next(
                (
                    post
                    for post in states[peer.index]["myPosts"]
                    if post.get("intent_id") in intent_ids
                ),
                None,
            )
            if own is None or peer_post is None:
                continue
            assessment = next(
                (
                    item
                    for item in owner_state["candidateAssessments"]
                    if item.get("task_id") == own.get("task_id")
                    and item.get("candidate_intent_id") == peer_post.get("intent_id")
                ),
                None,
            )
            if assessment is not None:
                return (owner, own, peer, peer_post), assessment, match_id
    return None


def _community_gate(user: ControlledUser, community_id: str) -> dict[str, Any]:
    before = _api(user, "GET", f"/api/app/communities/{community_id}")
    serialized = json.dumps(before)
    if "@example.com" in serialized or "owner_uid" in serialized:
        raise RuntimeError("Community detail leaked a private identity field")
    answer = _api(
        user,
        "POST",
        f"/api/app/communities/{community_id}/agent/query",
        {"question": "What privacy and safety rules apply here?"},
    )
    if "rules" not in str(answer.get("answer") or "").casefold():
        raise RuntimeError("Community Agent did not answer from Community rules")
    _api(user, "POST", f"/api/app/communities/{community_id}/leave", {})
    left = _api(user, "GET", f"/api/app/communities/{community_id}")
    if left.get("viewer", {}).get("joined") is True:
        raise RuntimeError("Community leave did not update authoritative membership")
    _api(
        user,
        "POST",
        f"/api/app/communities/{community_id}/join",
        {"invite_token": None},
    )
    rejoined = _api(user, "GET", f"/api/app/communities/{community_id}")
    if rejoined.get("viewer", {}).get("joined") is not True:
        raise RuntimeError("Community rejoin did not restore membership")
    return {
        "left_and_rejoined": True,
        "community_agent_scope": answer.get("scope"),
        "private_field_leak": False,
    }


def _room_gate(
    owner: ControlledUser,
    peer: ControlledUser,
    outsider: ControlledUser,
    *,
    candidate_room_id: str,
    shared_room_id: str,
) -> dict[str, Any]:
    candidate = _api(owner, "GET", f"/api/app/rooms/{candidate_room_id}")
    if candidate["channel_permissions"]["AGENTS_ONLY"]["write"] is not False:
        raise RuntimeError("Agents-only channel incorrectly allowed human writes")
    _expect_status(
        outsider, "GET", f"/api/app/rooms/{candidate_room_id}", 403
    )
    _expect_status(
        owner,
        "POST",
        f"/api/app/rooms/{candidate_room_id}/channels/AGENTS_ONLY/messages",
        403,
        {
            "content": "A human must not write into the Agents-only channel.",
            "authorship": "HUMAN_WRITTEN",
            "idempotency_key": "matrix-agents-only-denial",
        },
    )
    private_marker = f"private-matrix-{uuid4().hex[:12]}"
    _api(
        owner,
        "POST",
        f"/api/app/rooms/{candidate_room_id}/channels/PRIVATE_USER_AGENT/messages",
        {
            "content": private_marker,
            "authorship": "HUMAN_WRITTEN",
            "idempotency_key": f"matrix-private-{uuid4().hex[:16]}",
        },
    )
    peer_view = _api(peer, "GET", f"/api/app/rooms/{candidate_room_id}")
    if private_marker in json.dumps(peer_view):
        raise RuntimeError("private owner instruction leaked to the peer")
    _expect_status(
        owner,
        "POST",
        f"/api/app/rooms/{candidate_room_id}/channels/SHARED_ROOM/messages",
        403,
        {
            "content": "This candidate Room is not shared yet.",
            "authorship": "HUMAN_WRITTEN",
            "idempotency_key": "matrix-shared-locked",
        },
    )
    # Keep the evidence marker unique without producing a random digit run that
    # could legitimately resemble a phone number to the outbound privacy guard.
    safe_suffix = uuid4().hex[:12].translate(
        str.maketrans("0123456789", "ghijklmnop")
    )
    shared_marker = f"shared-matrix-{safe_suffix}"
    _api(
        owner,
        "POST",
        f"/api/app/rooms/{shared_room_id}/channels/SHARED_ROOM/messages",
        {
            "content": shared_marker,
            "authorship": "HUMAN_WRITTEN",
            "idempotency_key": f"matrix-shared-{uuid4().hex[:16]}",
        },
    )
    shared = _api(peer, "GET", f"/api/app/rooms/{shared_room_id}")
    if shared_marker not in json.dumps(shared["channels"]["SHARED_ROOM"]):
        raise RuntimeError("shared human message was not visible to the peer")
    _expect_status(outsider, "GET", f"/api/app/rooms/{shared_room_id}", 403)
    return {
        "candidate_room": candidate_room_id,
        "shared_room": shared_room_id,
        "private_instruction_leak": False,
        "agents_only_human_status": 403,
        "locked_shared_status": 403,
        "outsider_status": 403,
        "shared_message_visible": True,
    }


def _match_gate(
    owner: ControlledUser,
    peer: ControlledUser,
    outsider: ControlledUser,
    *,
    match_id: str,
) -> dict[str, Any]:
    detail = _api(owner, "GET", f"/api/app/matches/{match_id}")
    shared_room_id = str(detail["shared_room"]["room_id"])
    _expect_status(outsider, "GET", f"/api/app/matches/{match_id}", 403)
    change = _api(
        owner,
        "POST",
        f"/api/app/matches/{match_id}/changes",
        {
            "summary": "Use a precise public-venue working-session time.",
            "terms": {
                "start_at": "2026-10-15T10:00:00+00:00",
                "end_at": "2026-10-15T11:00:00+00:00",
                "location": "Public conference lobby",
            },
        },
    )["changeProposal"]
    version = int(change["version"])
    first = _api(
        owner,
        "POST",
        f"/api/app/matches/{match_id}/changes/{change['change_id']}/approve",
        {
            "version": version,
            "confirmation": f"APPROVE CHANGE VERSION {version}",
        },
    )
    if first.get("status") != "WAITING_FOR_PEER":
        raise RuntimeError("first change approval did not wait for the peer")
    second = _api(
        peer,
        "POST",
        f"/api/app/matches/{match_id}/changes/{change['change_id']}/approve",
        {
            "version": version,
            "confirmation": f"APPROVE CHANGE VERSION {version}",
        },
    )
    if second.get("status") != "MATCH_UPDATED":
        raise RuntimeError("dual change approval did not update the Match")
    calendar = _raw(owner, "GET", f"/api/app/matches/{match_id}/calendar.ics")
    if calendar.status_code != 200 or "BEGIN:VCALENDAR" not in calendar.text:
        raise RuntimeError("Match calendar export was not a valid VCALENDAR")
    offer = _api(
        owner,
        "PUT",
        f"/api/app/matches/{match_id}/contacts/mine",
        {"public_email": "controlled-contact@example.invalid"},
    )["contactCard"]
    cards = _api(peer, "GET", f"/api/app/matches/{match_id}/contacts")[
        "contactCards"
    ]
    card = next(
        item for item in cards if item["contact_card_id"] == offer["contact_card_id"]
    )
    accepted = _api(
        peer,
        "POST",
        f"/api/app/matches/{match_id}/contacts/{card['contact_card_id']}/accept",
        {},
    )
    if accepted.get("acceptance", {}).get("status") != "ACCEPTED":
        raise RuntimeError("peer did not explicitly accept the Contact Card")
    return {
        "match_id": match_id,
        "shared_room_id": shared_room_id,
        "change_version": version,
        "dual_change_approval": True,
        "calendar_valid": True,
        "contact_offer_accepted": True,
        "outsider_status": 403,
    }


def _memory_notification_autonomy_gate(user: ControlledUser) -> dict[str, Any]:
    memory_workspace = _api(user, "GET", "/api/app/memories")
    memories = memory_workspace["memories"]
    memory = next(
        (item for item in memories if item.get("status") == "PROPOSED"),
        None,
    )
    confirmation_performed = memory is not None
    if memory is None:
        memory = next(
            (item for item in memories if item.get("status") == "CONFIRMED"),
            None,
        )
    if memory is None:
        raise RuntimeError("candidate user has no reviewable Memory")
    memory_id = str(memory["memory_id"])
    confirmed = (
        _api(
            user,
            "POST",
            f"/api/app/memories/{memory_id}/actions",
            {"action": "CONFIRM"},
        )
        if confirmation_performed
        else {"memory": memory}
    )
    if confirmed["memory"].get("status") != "CONFIRMED":
        raise RuntimeError("proposed Memory was not explicitly confirmed")
    restricted = _api(
        user,
        "POST",
        f"/api/app/memories/{memory_id}/actions",
        {"action": "RESTRICT_SCOPE", "scope": "ROOM_SHARE"},
    )
    if restricted["memory"].get("scope") != "ROOM_SHARE":
        raise RuntimeError("Memory scope restriction was not persisted")
    disabled = _api(
        user,
        "POST",
        f"/api/app/memories/{memory_id}/actions",
        {"action": "TEMPORARILY_DISABLE"},
    )
    if disabled["memory"].get("disabled") is not True:
        raise RuntimeError("Memory temporary disable did not persist")
    _api(
        user,
        "POST",
        f"/api/app/memories/{memory_id}/actions",
        {"action": "ENABLE"},
    )
    _expect_status(
        user,
        "PUT",
        "/api/app/autonomy",
        422,
        {
            "action_levels": {
                "APPROVE_FINAL_COMMITMENT": "AUTOMATIC",
            },
            "task_id": None,
        },
    )
    automatic = _api(
        user,
        "PUT",
        "/api/app/autonomy",
        {
            "action_levels": {"PUBLISH_POST": "AUTOMATIC"},
            "task_id": None,
        },
    )
    levels = automatic["action_levels"]
    if levels["PUBLISH_POST"] != "AUTOMATIC":
        raise RuntimeError("automatic publish policy was not persisted")
    if levels["APPROVE_FINAL_COMMITMENT"] != "ASK_FIRST":
        raise RuntimeError("final commitment incorrectly became automatic")
    never = _api(
        user,
        "PUT",
        "/api/app/autonomy",
        {"action_levels": {"PUBLISH_POST": "NEVER"}, "task_id": None},
    )
    if never["action_levels"]["PUBLISH_POST"] != "NEVER":
        raise RuntimeError("NEVER autonomy policy was not persisted")
    notifications = _api(user, "GET", "/api/app/notifications")
    items = notifications["notifications"]
    if items:
        notification_id = str(items[0]["notification_id"])
        _api(
            user,
            "PUT",
            f"/api/app/notifications/{notification_id}/read",
            {},
        )
        _api(
            user,
            "PUT",
            f"/api/app/notifications/{notification_id}/archived",
            {},
        )
    _api(user, "PUT", "/api/app/notifications/read-all", {})
    return {
        "memory_confirmed": True,
        "confirmation_performed": confirmation_performed,
        "memory_scope": "ROOM_SHARE",
        "memory_disable_enable": True,
        "publish_automatic_saved": True,
        "publish_never_saved": True,
        "final_commitment_locked": "ASK_FIRST",
        "notifications_processed": len(items),
    }


def main() -> None:
    _assert_candidate_target()
    users = _users(_firebase_api_key(_admin_session()))
    states = _states(users)
    active = _active_context(users, states)
    if active is None:
        owner, own, peer, peer_post = _open_pair(users, states)
        assessment = _contact_pairs([(owner, own, peer, peer_post)])[0]
        plan = _approve_plan(owner, peer, str(own["task_id"]), assessment)
        match_id = str(plan["match_id"])
    else:
        (owner, own, peer, peer_post), assessment, match_id = active
    outsider = next(user for user in users if user.uid not in {owner.uid, peer.uid})
    match = _match_gate(owner, peer, outsider, match_id=match_id)
    room = _room_gate(
        owner,
        peer,
        outsider,
        candidate_room_id=str(
            assessment.get("room_id") or assessment["active_room_id"]
        ),
        shared_room_id=str(match["shared_room_id"]),
    )
    community = _community_gate(owner, str(own["community_id"]))
    controls = _memory_notification_autonomy_gate(owner)
    report = _api(
        owner,
        "POST",
        "/api/app/reports",
        {
            "target_type": "POST",
            "target_id": str(peer_post["intent_id"]),
            "category": "OTHER",
            "details": "Controlled candidate report for moderation acceptance.",
        },
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "candidate_url": BASE_URL,
                "authenticated_users_exercised": 3,
                "community": community,
                "room": room,
                "match": match,
                "memory_notifications_autonomy": controls,
                "report_id": report["report_id"],
                "passwords_printed": False,
                "tokens_printed": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
