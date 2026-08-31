"""Five-user live acceptance for the deployed PairPilot V1 candidate."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import firebase_admin
from firebase_admin import auth

BASE_URL = os.environ["PAIRPILOT_BASE_URL"].rstrip("/")
FIREBASE_API_KEY = os.environ["PAIRPILOT_FIREBASE_API_KEY"]
TEST_PASSWORD = os.environ["PAIRPILOT_TEST_PASSWORD"]
RUN_SUFFIX = os.getenv(
    "PAIRPILOT_ACCEPTANCE_SUFFIX", datetime.now(UTC).strftime("%Y%m%d%H%M%S")
)


@dataclass
class TestUser:
    index: int
    email: str
    uid: str
    token: str
    task_id: str = ""
    intent_id: str = ""


def _request(
    method: str,
    url: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
    timeout: int = 180,
) -> tuple[int, dict[str, Any] | str]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode()
            content_type = response.headers.get("Content-Type", "")
            return response.status, (
                json.loads(raw) if "application/json" in content_type else raw
            )
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload: dict[str, Any] | str = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        return exc.code, payload


def api(
    user: TestUser,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    expected: int = 200,
) -> dict[str, Any]:
    status, payload = _request(method, f"{BASE_URL}{path}", token=user.token, body=body)
    if status != expected:
        raise AssertionError(
            f"{method} {path}: expected {expected}, got {status}: {payload}"
        )
    assert isinstance(payload, dict)
    return payload


def create_or_update_user(index: int) -> TestUser:
    email = f"pairpilot-v1-{RUN_SUFFIX}-user{index}@example.com"
    try:
        record = auth.get_user_by_email(email)
        auth.update_user(record.uid, password=TEST_PASSWORD, email_verified=True)
    except auth.UserNotFoundError:
        record = auth.create_user(
            email=email,
            password=TEST_PASSWORD,
            email_verified=True,
            display_name=f"V1 User {index}",
        )
    status, signed_in = _request(
        "POST",
        (
            "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
            f"?key={FIREBASE_API_KEY}"
        ),
        body={"email": email, "password": TEST_PASSWORD, "returnSecureToken": True},
    )
    if status != 200 or not isinstance(signed_in, dict):
        raise AssertionError(f"Firebase sign-in failed for user {index}: {signed_in}")
    return TestUser(
        index=index, email=email, uid=record.uid, token=str(signed_in["idToken"])
    )


def onboard(user: TestUser) -> None:
    api(user, "POST", "/api/app/provision", {})
    api(
        user,
        "PUT",
        "/api/app/onboarding",
        {
            "display_name": f"V1 User {user.index}",
            "timezone": "Asia/Shanghai",
            "general_location": "Seoul",
            "language": "English",
            "adult_confirmed": True,
            "public_profile_visible": True,
            "default_autonomy_mode": "COPILOT",
            "public_sharing_policy": "Ask before every public Post.",
            "agent_sharing_policy": "Share minimum task-scoped evidence only.",
            "always_ask_policy": "Always ask before commitment or contact disclosure.",
            "community_ids": ["community_icml_seoul_2026"],
            "default_public_visibility": "COMMUNITY",
            "default_agent_visibility": "MINIMUM_NECESSARY",
            "notification_preference": "IN_APP",
        },
    )


def create_task(user: TestUser) -> None:
    result = api(
        user,
        "POST",
        "/api/app/tasks",
        {
            "title": f"V1 live room share {user.index}",
            "task_type": "ROOM_SHARE",
            "goal": (
                "Find a compatible adult ICML room-share partner for user "
                f"{user.index}. Private instruction code "
                f"PRIVATE-{RUN_SUFFIX}-{user.index} must never be shared."
            ),
            "event": "ICML",
            "location": "Seoul",
            "date_start": "2026-07-06",
            "date_end": "2026-07-10" if user.index % 2 else "2026-07-09",
            "public_requirements": ["Adult ICML attendee", "Quiet nights"],
            "maximum_additional_cost_usd": 70 + user.index,
            "partial_date_overlap_allowed": True,
            "community_id": "community_icml_seoul_2026",
        },
    )
    user.task_id = str(result["task"]["task_id"])
    user.intent_id = str(result["task"]["intent_id"])
    api(
        user,
        "POST",
        f"/api/app/tasks/{user.task_id}/publish",
        {
            "public_title": f"ICML Seoul room share option {user.index}",
            "public_summary": (
                "Adult attendee seeking a quiet, compatible room-share plan."
            ),
            "public_requirements": ["Adult ICML attendee", "Quiet nights"],
        },
    )


def bootstrap(user: TestUser) -> dict[str, Any]:
    return api(user, "GET", "/api/app/bootstrap")


def wait_for_candidate_pool(
    user: TestUser, minimum: int, timeout_seconds: int = 420
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    latest: dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = bootstrap(user)
        candidates = [
            item
            for item in latest.get("candidateAssessments", [])
            if item.get("task_id") == user.task_id
        ]
        if len(candidates) >= minimum:
            return latest
        time.sleep(10)
    raise AssertionError(
        f"user {user.index} candidate pool did not reach {minimum}: "
        f"{len(latest.get('candidateAssessments', []))}"
    )


def main() -> None:
    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            options={"projectId": os.environ["GOOGLE_CLOUD_PROJECT"]}
        )
    users = [create_or_update_user(index) for index in range(1, 6)]
    for user in users:
        onboard(user)
    for user in users[:4]:
        create_task(user)
    before_fifth = bootstrap(users[0])
    before_count = len(before_fifth.get("candidateAssessments", []))
    create_task(users[4])
    pool = wait_for_candidate_pool(users[0], minimum=3)
    candidates = sorted(
        [
            item
            for item in pool["candidateAssessments"]
            if item.get("task_id") == users[0].task_id
        ],
        key=lambda item: int(item.get("current_rank", 999)),
    )
    if len({item["candidate_intent_id"] for item in candidates}) < 3:
        raise AssertionError("candidate pool did not contain three independent intents")
    if not pool.get("candidateRankEvents"):
        raise AssertionError("rank-change events were not visible to the owner")
    private_code = f"PRIVATE-{RUN_SUFFIX}-1"
    rooms = pool.get("rooms", [])
    for room in rooms:
        room_payload = api(users[0], "GET", f"/api/app/rooms/{room['room_id']}")
        if private_code in json.dumps(room_payload):
            raise AssertionError("private task instruction leaked into Agent Room")
    status, _ = _request(
        "GET",
        f"{BASE_URL}/api/app/tasks/{users[0].task_id}",
        token=users[1].token,
    )
    if status != 403:
        raise AssertionError(f"cross-user task read returned {status}, expected 403")
    chosen = candidates[0]
    proposal_result = api(
        users[0],
        "POST",
        (
            f"/api/app/tasks/{users[0].task_id}/candidates/"
            f"{chosen['candidate_intent_id']}/proposal"
        ),
        {},
    )
    proposal = proposal_result["proposal"]
    candidate_user = next(
        user for user in users if user.intent_id == chosen["candidate_intent_id"]
    )
    for participant in (users[0], candidate_user):
        api(
            participant,
            "POST",
            f"/api/app/proposals/{proposal['proposal_id']}/approve",
            {
                "proposal_version": proposal["version"],
                "confirmation": f"APPROVE VERSION {proposal['version']}",
            },
        )
    matched = bootstrap(users[0])
    match = next(
        item
        for item in matched["matches"]
        if item["match_id"] == proposal["proposal_id"]
    )
    api(
        users[0],
        "PUT",
        f"/api/app/matches/{match['match_id']}/contacts/mine",
        {
            "wechat": f"pairpilot-v1-{RUN_SUFFIX}",
            "public_email": None,
            "phone": None,
            "whatsapp": None,
            "telegram": None,
            "linkedin": None,
            "other_handle": None,
        },
    )
    peer_contacts = api(
        candidate_user,
        "GET",
        f"/api/app/matches/{match['match_id']}/contacts",
    )
    if not peer_contacts["contactCards"]:
        raise AssertionError("explicit contact card was not visible after Match")
    room_id = str(match["room_id"])
    api(
        users[0],
        "POST",
        f"/api/app/rooms/{room_id}/messages",
        {
            "content": "Hello from the live shared Room.",
            "authorship": "HUMAN_WRITTEN",
            "idempotency_key": f"live-{RUN_SUFFIX}",
        },
    )
    final_bootstrap = bootstrap(users[0])
    memory = next(
        item
        for item in final_bootstrap["memories"]
        if item.get("match_id") == match["match_id"]
    )
    api(
        users[0],
        "POST",
        f"/api/app/memories/{memory['memory_id']}/actions",
        {"action": "CONFIRM"},
    )
    api(
        users[0],
        "POST",
        f"/api/app/matches/{match['match_id']}/outcome",
        {
            "did_plan_happen": True,
            "would_coordinate_again": True,
            "agreed_term_inaccurate": False,
            "optional_feedback": "Private live acceptance feedback.",
        },
    )
    report_target = users[3]
    api(
        users[4],
        "POST",
        "/api/app/reports",
        {
            "target_type": "POST",
            "target_id": report_target.intent_id,
            "category": "OTHER",
            "details": "Live safety acceptance report.",
        },
    )
    report_post = next(
        item
        for item in bootstrap(users[4])["explorePosts"]
        if item["intent_id"] == report_target.intent_id
    )
    api(
        users[4],
        "POST",
        "/api/app/blocks",
        {
            "target_agent_id": report_post["owner_agent_id"],
            "reason": "Live acceptance block",
        },
    )
    api(
        users[4],
        "POST",
        "/api/app/account/delete",
        {"confirmation": "DELETE MY PAIRPILOT ACCOUNT"},
    )
    evidence = {
        "status": "PASS",
        "run_suffix": RUN_SUFFIX,
        "independently_authenticated_users": len(users),
        "candidate_count": len(candidates),
        "candidate_count_before_fifth_post": before_count,
        "rank_event_count": len(pool.get("candidateRankEvents", [])),
        "offline_new_post_observed": len(candidates) > before_count,
        "cross_user_task_read_status": 403,
        "match_id": match["match_id"],
        "shared_room_id": room_id,
        "contact_card_verified": True,
        "memory_confirmed": True,
        "outcome_recorded": True,
        "block_report_delete_verified": True,
    }
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"V1 live acceptance failed: {type(exc).__name__}: {exc}", file=sys.stderr
        )
        raise
