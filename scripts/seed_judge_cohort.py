"""Create the isolated, visibly-labelled PairPilot judge cohort through real APIs.

Passwords are rotated on every run and printed once for the local gitignored judge
guide. The script never writes credentials to the repository or Firestore.
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
COMMUNITY_ID = "community_agent_builders"
ACCOUNT_SUFFIX = os.getenv("PAIRPILOT_JUDGE_ACCOUNT_SUFFIX", "").strip()


@dataclass
class JudgeUser:
    key: str
    label: str
    email: str
    password: str
    uid: str = ""
    token: str = ""


def admin_session() -> AuthorizedSession:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return AuthorizedSession(credentials)


def firebase_api_key(session: AuthorizedSession) -> str:
    apps = session.get(
        f"https://firebase.googleapis.com/v1beta1/projects/{PROJECT}/webApps",
        params={"pageSize": 100},
        timeout=30,
    ).json()["apps"]
    app_id = next(
        item["appId"]
        for item in apps
        if item["displayName"] == "PairPilot Public Beta Web"
    )
    return str(
        session.get(
            f"https://firebase.googleapis.com/v1beta1/projects/{PROJECT}/webApps/"
            f"{app_id}/config",
            timeout=30,
        ).json()["apiKey"]
    )


def sign_in(email: str, password: str, api_key: str) -> str:
    response = requests.post(
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
        params={"key": api_key},
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=30,
    )
    response.raise_for_status()
    return str(response.json()["idToken"])


def api(
    user: JudgeUser,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    expected: tuple[int, ...] = (200,),
    timeout: int = 300,
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
            f"{user.key} {method} {path}: HTTP {response.status_code} "
            f"{response.text[:1200]}"
        )
    return dict(response.json())


def provision(user: JudgeUser, api_key: str) -> None:
    try:
        record = auth.get_user_by_email(user.email)
        record = auth.update_user(
            record.uid,
            password=user.password,
            email_verified=True,
            display_name=user.label,
            disabled=False,
        )
    except auth.UserNotFoundError:
        record = auth.create_user(
            email=user.email,
            password=user.password,
            email_verified=True,
            display_name=user.label,
        )
    user.uid = record.uid
    user.token = sign_in(user.email, user.password, api_key)
    api(user, "POST", "/api/app/provision", {})
    api(
        user,
        "PUT",
        "/api/app/onboarding",
        {
            "display_name": user.label,
            "timezone": "Europe/London",
            "general_location": "London",
            "language": "English",
            "adult_confirmed": True,
            "public_profile_visible": True,
            "default_autonomy_mode": "COPILOT",
            "public_sharing_policy": "Ask before publishing every public Post.",
            "agent_sharing_policy": "Share minimum task-scoped evidence only.",
            "always_ask_policy": (
                "Always ask before commitment, contact disclosure, payment, or booking."
            ),
            "community_ids": [COMMUNITY_ID],
            "default_public_visibility": "COMMUNITY",
            "default_agent_visibility": "MINIMUM_NECESSARY",
            "notification_preference": "IN_APP",
        },
    )


def create_task(
    user: JudgeUser,
    *,
    title: str,
    task_type: str,
    goal: str,
    event: str,
    location: str,
    date_start: str,
    date_end: str,
    requirements: list[str],
    publish: bool = True,
) -> dict[str, Any]:
    created = api(
        user,
        "POST",
        "/api/app/tasks",
        {
            "title": title,
            "task_type": task_type,
            "goal": goal,
            "event": event,
            "location": location,
            "date_start": date_start,
            "date_end": date_end,
            "public_requirements": requirements,
            "maximum_additional_cost_usd": 20,
            "partial_date_overlap_allowed": True,
            "community_id": COMMUNITY_ID,
        },
    )["task"]
    if publish:
        api(
            user,
            "POST",
            f"/api/app/tasks/{created['task_id']}/publish",
            {
                "public_title": title,
                "public_summary": goal.split(" Private judge canary", 1)[0],
                "public_requirements": requirements,
            },
        )
    return dict(created)


def contact(owner: JudgeUser, task_id: str, candidate_intent_id: str) -> None:
    state = api(owner, "GET", "/api/app/bootstrap")
    existing = next(
        (
            item
            for item in state["candidateAssessments"]
            if item.get("task_id") == task_id
            and item.get("candidate_intent_id") == candidate_intent_id
        ),
        None,
    )
    if existing is None:
        api(
            owner,
            "POST",
            f"/api/app/tasks/{task_id}/candidates/{candidate_intent_id}/contact",
            {},
        )


def wait_for_candidate(
    owner: JudgeUser, task_id: str, candidate_intent_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    deadline = time.monotonic() + 180
    latest: dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = api(owner, "GET", "/api/app/bootstrap")
        candidate = next(
            (
                item
                for item in latest["candidateAssessments"]
                if item.get("task_id") == task_id
                and item.get("candidate_intent_id") == candidate_intent_id
            ),
            None,
        )
        if candidate is not None:
            return latest, candidate
        time.sleep(5)
    raise RuntimeError(f"candidate {candidate_intent_id} not ready for {task_id}")


def create_proposal(
    owner: JudgeUser, task_id: str, candidate: dict[str, Any]
) -> tuple[str, int]:
    if candidate.get("proposal_id"):
        state = api(owner, "GET", "/api/app/bootstrap")
        decision = next(
            item
            for item in state["decisions"]
            if item.get("proposal_id") == candidate["proposal_id"]
        )
        return str(candidate["proposal_id"]), int(decision["proposal_version"])
    proposal = api(
        owner,
        "POST",
        f"/api/app/tasks/{task_id}/candidates/"
        f"{candidate['candidate_intent_id']}/proposal",
        {},
    )["proposal"]
    return str(proposal["proposal_id"]), int(proposal["version"])


def approve(user: JudgeUser, proposal_id: str, version: int) -> dict[str, Any]:
    return api(
        user,
        "POST",
        f"/api/app/proposals/{proposal_id}/approve",
        {
            "proposal_version": version,
            "confirmation": f"APPROVE VERSION {version}",
        },
    )


def main() -> None:
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": PROJECT})
    api_key = firebase_api_key(admin_session())
    definitions = (
        ("requester", "Judge Requester · Controlled test account"),
        ("candidate_a", "Candidate A · Controlled test account"),
        ("candidate_b", "Candidate B · Controlled test account"),
        ("candidate_c", "Candidate C · Controlled test account"),
        ("late_candidate", "Late Candidate · Controlled test account"),
        ("fresh_requester", "Fresh Requester · Controlled test account"),
    )
    users: dict[str, JudgeUser] = {}
    for key, label in definitions:
        email_key = key.replace("_", "-")
        if ACCOUNT_SUFFIX:
            email_key = f"{email_key}-{ACCOUNT_SUFFIX}"
        user = JudgeUser(
            key=key,
            label=label,
            email=f"pairpilot-{email_key}@example.com",
            password="Pp!" + secrets.token_urlsafe(24),
        )
        provision(user, api_key)
        users[key] = user

    requester = users["requester"]
    candidate_a = users["candidate_a"]
    coffee_common = {
        "task_type": "COFFEE_CHAT",
        "event": "All Things Agentic founder coffee",
        "location": "London Shoreditch",
        "date_start": "2026-09-08",
        "date_end": "2026-09-08",
        "requirements": [
            "Adult AI builder",
            "Available 15:00–17:00",
            "Interested in agent interoperability",
        ],
    }
    candidate_posts: dict[str, dict[str, Any]] = {}
    for key, angle in (
        ("candidate_a", "product and multi-agent UX"),
        ("candidate_b", "A2A protocols and infrastructure"),
        ("candidate_c", "founder feedback and go-to-market"),
    ):
        candidate_posts[key] = create_task(
            users[key],
            title=f"Controlled demo: founder coffee — {key[-1].upper()}",
            goal=(
                f"Meet another adult Agent builder to discuss {angle}. "
                f"Private judge canary PRIVATE-JUDGE-{key} must never be shared."
            ),
            **coffee_common,
        )
    late_task = create_task(
        users["late_candidate"],
        title="Controlled demo: late candidate draft",
        goal=(
            "Join the same founder coffee after the initial ranking to demonstrate "
            "continuous discovery. Private judge canary PRIVATE-JUDGE-LATE must "
            "never be shared."
        ),
        publish=False,
        **coffee_common,
    )
    active_task = create_task(
        requester,
        title="Controlled demo: find three founder coffee candidates",
        goal=(
            "Find and rank several adult Agent builders for a focused coffee chat. "
            "Private judge canary PRIVATE-JUDGE-REQUESTER must never be shared."
        ),
        **coffee_common,
    )
    for key in ("candidate_a", "candidate_b", "candidate_c"):
        contact(
            requester,
            str(active_task["task_id"]),
            str(candidate_posts[key]["intent_id"]),
        )
    expected_intents = {
        candidate_posts[key]["intent_id"]
        for key in ("candidate_a", "candidate_b", "candidate_c")
    }
    active_state = api(requester, "GET", "/api/app/bootstrap")
    active_candidates = [
        item
        for item in active_state["candidateAssessments"]
        if item.get("task_id") == active_task["task_id"]
        and item.get("candidate_intent_id") in expected_intents
    ]
    if len(active_candidates) != 3:
        raise RuntimeError(
            f"expected 3 active candidates, got {len(active_candidates)}"
        )
    a_active = next(
        item
        for item in active_candidates
        if item["candidate_intent_id"] == candidate_posts["candidate_a"]["intent_id"]
    )
    pending_proposal_id, pending_version = create_proposal(
        requester, str(active_task["task_id"]), a_active
    )
    pending_result = approve(requester, pending_proposal_id, pending_version)

    meal_common = {
        "task_type": "MEAL_COMPANION",
        "event": "Post-hackathon dinner",
        "location": "London King's Cross",
        "date_start": "2026-09-09",
        "date_end": "2026-09-09",
        "requirements": ["Adult", "Available 18:30–20:00", "Split the bill"],
    }
    meal_peer = create_task(
        candidate_a,
        title="Controlled demo: candidate dinner companion",
        goal=(
            "Have a relaxed post-hackathon dinner and split the bill. "
            "Private judge canary PRIVATE-MEAL-A must never be shared."
        ),
        **meal_common,
    )
    meal_owner = create_task(
        requester,
        title="Controlled demo: completed dinner match",
        goal=(
            "Find a compatible adult dinner companion and split the bill. "
            "Private judge canary PRIVATE-MEAL-REQUESTER must never be shared."
        ),
        **meal_common,
    )
    contact(requester, str(meal_owner["task_id"]), str(meal_peer["intent_id"]))
    _, meal_candidate = wait_for_candidate(
        requester, str(meal_owner["task_id"]), str(meal_peer["intent_id"])
    )
    completed_proposal_id, completed_version = create_proposal(
        requester, str(meal_owner["task_id"]), meal_candidate
    )
    approve(requester, completed_proposal_id, completed_version)
    approve(candidate_a, completed_proposal_id, completed_version)

    final = api(requester, "GET", "/api/app/bootstrap")
    match = next(
        item for item in final["matches"] if item["match_id"] == completed_proposal_id
    )
    api(
        candidate_a,
        "PUT",
        f"/api/app/matches/{completed_proposal_id}/contacts/mine",
        {
            "public_email": None,
            "phone": None,
            "whatsapp": None,
            "telegram": None,
            "wechat": None,
            "linkedin": None,
            "other_handle": "Controlled demo contact — Candidate A",
        },
    )
    api(
        candidate_a,
        "POST",
        f"/api/app/rooms/{match['room_id']}/messages",
        {
            "content": (
                "Hello from Candidate A. This is a controlled demo human message "
                "inside the unlocked Shared Room."
            ),
            "authorship": "HUMAN_WRITTEN",
            "idempotency_key": "judge-cohort-candidate-a-welcome-v1",
        },
    )
    final = api(requester, "GET", "/api/app/bootstrap")
    memory = next(
        (
            item
            for item in final["memories"]
            if item.get("match_id") == completed_proposal_id
        ),
        None,
    )
    if memory and memory.get("status") != "CONFIRMED":
        api(
            requester,
            "POST",
            f"/api/app/memories/{memory['memory_id']}/actions",
            {"action": "CONFIRM"},
        )
    final = api(requester, "GET", "/api/app/bootstrap")
    output = {
        "status": "PASS",
        "accounts": {
            key: {
                "label": user.label,
                "email": user.email,
                "password": user.password,
                "uid": user.uid,
            }
            for key, user in users.items()
        },
        "active_task_id": active_task["task_id"],
        "active_intent_id": active_task["intent_id"],
        "active_candidate_count": len(active_candidates),
        "pending_proposal_id": pending_proposal_id,
        "pending_proposal_version": pending_version,
        "pending_first_approval_status": pending_result.get("status"),
        "completed_task_id": meal_owner["task_id"],
        "completed_match_id": completed_proposal_id,
        "shared_room_id": match["room_id"],
        "late_candidate_task_id": late_task["task_id"],
        "requester_rooms": len(final["rooms"]),
        "requester_matches": len(final["matches"]),
        "requester_relationships": len(final["relationships"]),
        "requester_confirmed_memories": len(
            [item for item in final["memories"] if item.get("status") == "CONFIRMED"]
        ),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
