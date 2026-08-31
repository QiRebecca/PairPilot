"""Seed one existing user with real API-created V1 multi-Agent experience data.

The script authenticates with Firebase custom tokens, so it never needs or stores the
target user's password. Simulated peers are labelled in their display names.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any

import firebase_admin
import google.auth
import requests
from firebase_admin import auth
from google.auth.transport.requests import AuthorizedSession

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
BASE_URL = os.environ["PAIRPILOT_BASE_URL"].rstrip("/")
TARGET_EMAIL = os.getenv("PAIRPILOT_TARGET_EMAIL", "qi.zhang.agi@gmail.com")
TARGET_PASSWORD = os.environ["PAIRPILOT_TARGET_PASSWORD"]


@dataclass
class User:
    uid: str
    token: str
    email: str
    display_name: str
    task_id: str = ""
    intent_id: str = ""


PEERS = (
    (
        "maya",
        "Maya Chen · simulated tester",
        "Disney photo and thrill-ride buddy",
        "I enjoy taking portraits, thrill rides, and splitting shared costs fairly.",
        ["Enjoys taking photos", "Thrill rides", "AA shared costs", "Easygoing"],
    ),
    (
        "lina",
        "Lina Zhou · simulated tester",
        "Relaxed Disneyland photo day",
        (
            "I prefer a relaxed pace, plenty of photo stops, and clear planning "
            "in advance."
        ),
        [
            "Enjoys taking photos",
            "Relaxed pace",
            "AA shared costs",
            "Good communicator",
        ],
    ),
    (
        "ava",
        "Ava Wong · simulated tester",
        "Disney food, parade and photo buddy",
        "I like character photos, parades, snacks, and a friendly low-pressure day.",
        ["Enjoys taking photos", "Parades and food", "AA shared costs", "Easygoing"],
    ),
)


def admin_session() -> AuthorizedSession:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return AuthorizedSession(credentials)


def firebase_api_key(session: AuthorizedSession) -> str:
    apps = session.get(
        f"https://firebase.googleapis.com/v1beta1/projects/{PROJECT}/webApps",
        params={"pageSize": 100},
    ).json()["apps"]
    app_id = next(
        item["appId"]
        for item in apps
        if item["displayName"] == "PairPilot Public Beta Web"
    )
    config = session.get(
        f"https://firebase.googleapis.com/v1beta1/projects/{PROJECT}/webApps/"
        f"{app_id}/config"
    ).json()
    return str(config["apiKey"])


def token_for_email(email: str, password: str, api_key: str) -> str:
    response = requests.post(
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        params={"key": api_key},
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=30,
    )
    response.raise_for_status()
    return str(response.json()["idToken"])


def call(
    user: User,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    expected: tuple[int, ...] = (200,),
    timeout: int = 240,
) -> dict[str, Any]:
    response = requests.request(
        method,
        BASE_URL + path,
        headers={
            "Authorization": f"Bearer {user.token}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=timeout,
    )
    if response.status_code not in expected:
        raise RuntimeError(
            f"{user.display_name} {method} {path}: HTTP {response.status_code} "
            f"{response.text[:1000]}"
        )
    return dict(response.json())


def onboard(user: User) -> None:
    call(user, "POST", "/api/app/provision", {})
    call(
        user,
        "PUT",
        "/api/app/onboarding",
        {
            "display_name": user.display_name,
            "timezone": "Asia/Shanghai",
            "general_location": "Hong Kong and Shanghai",
            "language": "Chinese and English",
            "adult_confirmed": True,
            "public_profile_visible": True,
            "default_autonomy_mode": "COPILOT",
            "public_sharing_policy": "Ask before publishing each public post.",
            "agent_sharing_policy": "Share minimum task-scoped evidence only.",
            "always_ask_policy": (
                "Always ask before contact disclosure, payment, booking, or commitment."
            ),
            "community_ids": ["community_icml_seoul_2026"],
            "default_public_visibility": "COMMUNITY",
            "default_agent_visibility": "MINIMUM_NECESSARY",
            "notification_preference": "IN_APP",
        },
    )


def ensure_peer_task(
    user: User,
    title: str,
    summary: str,
    requirements: list[str],
    source_constraints: dict[str, Any],
) -> None:
    state = call(user, "GET", "/api/app/bootstrap")
    compatible_title = f"{title} · integrated"
    existing = next(
        (
            item
            for item in state["tasks"]
            if item.get("title") == compatible_title
        ),
        None,
    )
    if existing is None:
        for post in state["myPosts"]:
            if post.get("status") == "OPEN":
                call(
                    user,
                    "PATCH",
                    f"/api/app/posts/{post['intent_id']}/status",
                    {"status": "CLOSED"},
                )
        created = call(
            user,
            "POST",
            "/api/app/tasks",
            {
                "title": compatible_title,
                "task_type": "EVENT_BUDDY",
                "goal": summary,
                "event": str(source_constraints["event"]),
                "location": str(source_constraints["location"]),
                "date_start": str(source_constraints["date_start"]),
                "date_end": str(source_constraints["date_end"]),
                "public_requirements": requirements,
                "maximum_additional_cost_usd": 0,
                "partial_date_overlap_allowed": True,
                "community_id": "community_icml_seoul_2026",
            },
        )["task"]
    else:
        created = existing
    user.task_id = str(created["task_id"])
    user.intent_id = str(created["intent_id"])
    call(
        user,
        "POST",
        f"/api/app/tasks/{user.task_id}/publish",
        {
            "public_title": title,
            "public_summary": summary,
            "public_requirements": requirements,
        },
    )


def main() -> None:
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": PROJECT})
    api_key = firebase_api_key(admin_session())
    target_record = auth.get_user_by_email(TARGET_EMAIL)
    qi = User(
        uid=target_record.uid,
        token=token_for_email(TARGET_EMAIL, TARGET_PASSWORD, api_key),
        email=TARGET_EMAIL,
        display_name="Qi Zhang",
    )
    call(qi, "POST", "/api/app/provision", {})
    qi_state = call(qi, "GET", "/api/app/bootstrap")
    disney_task = next(
        (
            item
            for item in qi_state["tasks"]
            if item.get("task_type") == "EVENT_BUDDY"
            and "迪士尼" in str(item.get("title", ""))
        ),
        None,
    )
    if disney_task is None:
        raise RuntimeError("The target account has no Hong Kong Disneyland request.")
    qi.task_id = str(disney_task["task_id"])
    qi.intent_id = str(disney_task["intent_id"])
    source_constraints = dict(disney_task.get("agent_public_draft", {}))
    required_constraint_fields = {"event", "location", "date_start", "date_end"}
    if not required_constraint_fields.issubset(source_constraints):
        raise RuntimeError("The Disneyland request is missing public constraints.")
    call(
        qi,
        "POST",
        f"/api/app/tasks/{qi.task_id}/publish",
        {
            "public_title": "9月10日香港迪士尼拍照搭子",
            "public_summary": (
                "想找一位性格随和、喜欢互相拍照的成年女生一起玩香港迪士尼。"
                "费用各自承担，具体项目和是否购买优速通可以一起商量。"
            ),
            "public_requirements": [
                "成年女生",
                "喜欢互相拍照",
                "性格随和",
                "费用AA",
                "项目可协商",
            ],
        },
    )
    for community_id in (
        "community_hk_disney_buddies",
        "community_agent_builders",
        "community_shanghai_weekend",
    ):
        call(
            qi,
            "POST",
            f"/api/app/communities/{community_id}/join",
            {},
            expected=(200,),
        )

    peers: list[User] = []
    for key, display_name, title, summary, requirements in PEERS:
        email = f"pairpilot-integrated-{key}@example.com"
        peer_password = secrets.token_urlsafe(24)
        try:
            record = auth.get_user_by_email(email)
            auth.update_user(
                record.uid,
                email_verified=True,
                display_name=display_name,
                password=peer_password,
            )
        except auth.UserNotFoundError:
            record = auth.create_user(
                email=email,
                email_verified=True,
                display_name=display_name,
                password=peer_password,
            )
        peer = User(
            uid=record.uid,
            token=token_for_email(email, peer_password, api_key),
            email=email,
            display_name=display_name,
        )
        onboard(peer)
        ensure_peer_task(
            peer, title, summary, requirements, source_constraints
        )
        peers.append(peer)

    qi_state = call(qi, "GET", "/api/app/bootstrap")
    existing_candidate_ids = {
        str(item["candidate_intent_id"])
        for item in qi_state["candidateAssessments"]
        if item.get("task_id") == qi.task_id
    }
    for peer in peers:
        if peer.intent_id not in existing_candidate_ids:
            call(
                qi,
                "POST",
                f"/api/app/tasks/{qi.task_id}/candidates/{peer.intent_id}/contact",
                {},
                timeout=300,
            )

    deadline = time.monotonic() + 120
    candidates: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        qi_state = call(qi, "GET", "/api/app/bootstrap")
        candidates = [
            item
            for item in qi_state["candidateAssessments"]
            if item.get("task_id") == qi.task_id
            and item.get("candidate_intent_id")
            in {peer.intent_id for peer in peers}
        ]
        if len(candidates) == len(peers):
            break
        time.sleep(5)
    if len(candidates) != len(peers):
        raise RuntimeError(f"Expected 3 integrated candidates, found {len(candidates)}")

    matched = next(
        (
            match
            for match in qi_state["matches"]
            if qi.uid in match.get("participant_uids", [])
        ),
        None,
    )
    selected_peer = peers[0]
    if matched is None:
        selected = next(
            item
            for item in candidates
            if item["candidate_intent_id"] == selected_peer.intent_id
        )
        if selected.get("proposal_id"):
            proposal_id = str(selected["proposal_id"])
            decision = next(
                item
                for item in qi_state["decisions"]
                if item.get("proposal_id") == proposal_id
            )
            version = int(decision["proposal_version"])
        else:
            proposal = call(
                qi,
                "POST",
                f"/api/app/tasks/{qi.task_id}/candidates/"
                f"{selected_peer.intent_id}/proposal",
                {},
            )["proposal"]
            proposal_id = str(proposal["proposal_id"])
            version = int(proposal["version"])
        approval = {
            "proposal_version": version,
            "confirmation": f"APPROVE VERSION {version}",
        }
        call(qi, "POST", f"/api/app/proposals/{proposal_id}/approve", approval)
        call(
            selected_peer,
            "POST",
            f"/api/app/proposals/{proposal_id}/approve",
            approval,
        )
        qi_state = call(qi, "GET", "/api/app/bootstrap")
        matched = next(
            item for item in qi_state["matches"] if item["match_id"] == proposal_id
        )

    match_id = str(matched["match_id"])
    room_id = str(matched["room_id"])
    call(
        selected_peer,
        "PUT",
        f"/api/app/matches/{match_id}/contacts/mine",
        {
            "public_email": None,
            "phone": None,
            "whatsapp": None,
            "telegram": None,
            "wechat": "PairPilot-Maya-Demo",
            "linkedin": None,
            "other_handle": "Simulated test contact",
        },
    )
    call(
        selected_peer,
        "POST",
        f"/api/app/rooms/{room_id}/messages",
        {
            "content": (
                "Hi Qi！我是 Maya（模拟测试用户）。我们的 Agent 已经确认了日期、"
                "拍照偏好和费用 AA；你可以直接在这个 Room 里回复我测试真人聊天。"
            ),
            "authorship": "HUMAN_WRITTEN",
            "idempotency_key": "qi-integrated-maya-welcome-v1",
        },
    )
    qi_state = call(qi, "GET", "/api/app/bootstrap")
    for memory in qi_state["memories"]:
        if memory.get("match_id") == match_id and memory.get("status") != "CONFIRMED":
            call(
                qi,
                "POST",
                f"/api/app/memories/{memory['memory_id']}/actions",
                {"action": "CONFIRM"},
            )
            break
    final = call(qi, "GET", "/api/app/bootstrap")
    evidence = {
        "status": "PASS",
        "target_uid": qi.uid,
        "task_id": qi.task_id,
        "simulated_peers": len(peers),
        "ranked_candidates": len(
            [
                item
                for item in final["candidateAssessments"]
                if item.get("task_id") == qi.task_id
            ]
        ),
        "rooms": len(final["rooms"]),
        "matches": len(final["matches"]),
        "relationships": len(final["relationships"]),
        "memories": len(final["memories"]),
        "communities_joined": len(final["communityMemberships"]),
        "notifications": len(final["notifications"]),
        "match_id": match_id,
        "shared_room_id": room_id,
    }
    print(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
