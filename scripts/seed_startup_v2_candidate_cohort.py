"""Seed ten real Firebase users and 25 Posts into isolated V2 candidate collections.

This script fails closed unless the target reports ``environment=candidate``.
Passwords are stored in Secret Manager and are never printed or written to Git.
It creates world facts only; candidate ranking, Agent conversations, proposals,
and Match outcomes must be produced by the generic runtime during acceptance.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
import secrets
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Keep this operator script runnable from a clean checkout without requiring an
# editable package install. The production image still imports installed
# packages normally; this path setup applies only to this local CLI process.
REPO_ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    REPO_ROOT / "packages" / "schemas",
    REPO_ROOT / "services" / "orchestrator",
    REPO_ROOT / "services" / "peer_agents",
):
    sys.path.insert(0, str(source_root))

import firebase_admin  # noqa: E402
import google.auth  # noqa: E402
import requests  # noqa: E402
from firebase_admin import auth  # noqa: E402
from google.auth.exceptions import TransportError  # noqa: E402
from google.auth.transport.requests import AuthorizedSession  # noqa: E402
from pairpilot_orchestrator.infrastructure.google_cloud import (  # noqa: E402
    GoogleCloudStore,
)

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
BASE_URL = os.environ.get("PAIRPILOT_CANDIDATE_BASE_URL", "").rstrip("/")
CONFIRMATION = os.environ.get("PAIRPILOT_COHORT_CONFIRM", "")
COLLECTION_PREFIX = "candidate_v2_"
EVENT_TOPIC = "pairpilot-v2-candidate-events"

COMMUNITIES = (
    {
        "community_id": "community_v2_ai_conference",
        "name": "AI Conference · Controlled Candidate",
        "description": "Controlled cohort for an AI conference in London.",
        "type": "CONFERENCE_EVENT",
        "location": "London, United Kingdom",
        "membership_type": "PUBLIC",
        "visibility": "PUBLIC",
        "membership_policy": "PUBLIC_JOIN",
    },
    {
        "community_id": "community_v2_university_orientation",
        "name": "University Orientation · Controlled Candidate",
        "description": "Controlled cohort for a university orientation week.",
        "type": "UNIVERSITY_EVENT",
        "location": "Cambridge, United Kingdom",
        "membership_type": "PUBLIC",
        "visibility": "PUBLIC",
        "membership_policy": "PUBLIC_JOIN",
    },
    {
        "community_id": "community_v2_local_weekends",
        "name": "Local Weekend Activities · Controlled Candidate",
        "description": "Controlled cohort for local weekend coordination.",
        "type": "LOCAL_INTEREST",
        "location": "London, United Kingdom",
        "membership_type": "PUBLIC",
        "visibility": "PUBLIC",
        "membership_policy": "PUBLIC_JOIN",
    },
)
TASK_TYPES = (
    "ROOM_SHARE",
    "MEAL_COMPANION",
    "COFFEE_CHAT",
    "EVENT_BUDDY",
    "HACKATHON_TEAMMATE",
)


@dataclass
class ControlledUser:
    index: int
    email: str
    display_name: str
    secret_id: str
    password: str = ""
    uid: str = ""
    token: str = ""


def _admin_session() -> AuthorizedSession:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return AuthorizedSession(credentials)


def _admin_request(
    session: AuthorizedSession,
    method: str,
    url: str,
    **kwargs: Any,
) -> requests.Response:
    """Retry bounded control-plane failures, including OAuth refresh timeouts."""

    kwargs.setdefault("timeout", 45)
    for attempt in range(4):
        try:
            return session.request(method, url, **kwargs)
        except (TransportError, requests.RequestException):
            if attempt == 3:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("unreachable Google control-plane retry state")


def _firebase_api_key(session: AuthorizedSession) -> str:
    apps_response = _admin_request(
        session,
        "GET",
        f"https://firebase.googleapis.com/v1beta1/projects/{PROJECT}/webApps",
        params={"pageSize": 100},
    )
    apps_response.raise_for_status()
    apps = apps_response.json()["apps"]
    app_id = next(
        item["appId"]
        for item in apps
        if item["displayName"] == "PairPilot Public Beta Web"
    )
    config = _admin_request(
        session,
        "GET",
        f"https://firebase.googleapis.com/v1beta1/projects/{PROJECT}/webApps/"
        f"{app_id}/config",
    )
    config.raise_for_status()
    return str(config.json()["apiKey"])


def _secret_password(session: AuthorizedSession, secret_id: str) -> str:
    secret_url = (
        f"https://secretmanager.googleapis.com/v1/projects/{PROJECT}/secrets/"
        f"{secret_id}"
    )
    latest = _admin_request(session, "GET", f"{secret_url}/versions/latest:access")
    if latest.ok:
        return base64.b64decode(latest.json()["payload"]["data"]).decode()
    if latest.status_code not in {400, 404}:
        latest.raise_for_status()
    existing = _admin_request(session, "GET", secret_url)
    if existing.status_code == 404:
        created = _admin_request(
            session,
            "POST",
            f"https://secretmanager.googleapis.com/v1/projects/{PROJECT}/secrets",
            params={"secretId": secret_id},
            json={"replication": {"automatic": {}}},
        )
        created.raise_for_status()
    elif not existing.ok:
        existing.raise_for_status()
    password = "Pp!" + secrets.token_urlsafe(28)
    version = _admin_request(
        session,
        "POST",
        f"{secret_url}:addVersion",
        json={"payload": {"data": base64.b64encode(password.encode()).decode()}},
    )
    version.raise_for_status()
    return password


def _sign_in(email: str, password: str, api_key: str) -> str:
    response: requests.Response | None = None
    for attempt in range(4):
        try:
            response = requests.post(
                "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
                params={"key": api_key},
                json={
                    "email": email,
                    "password": password,
                    "returnSecureToken": True,
                },
                timeout=45,
            )
            break
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 3:
                raise
            time.sleep(2**attempt)
    if response is None:  # pragma: no cover - defensive assertion
        raise RuntimeError("Firebase sign-in did not produce a response")
    response.raise_for_status()
    return str(response.json()["idToken"])


def _api(
    user: ControlledUser,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    expected: tuple[int, ...] = (200,),
    retry_transport: bool = False,
) -> dict[str, Any]:
    attempts = 3 if retry_transport else 1
    response: requests.Response | None = None
    for attempt in range(attempts):
        try:
            response = requests.request(
                method,
                BASE_URL + path,
                headers={
                    "Authorization": f"Bearer {user.token}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=45,
            )
            break
        except (requests.ConnectionError, requests.Timeout):
            if attempt + 1 >= attempts:
                raise
            time.sleep(2**attempt)
    if response is None:  # pragma: no cover - defensive assertion
        raise RuntimeError("candidate request did not produce a response")
    if response.status_code not in expected:
        raise RuntimeError(
            f"user-{user.index:02d} {method} {path}: "
            f"HTTP {response.status_code} {response.text[:600]}"
        )
    return dict(response.json())


def _assert_candidate_target() -> None:
    if not PROJECT or not BASE_URL:
        raise RuntimeError(
            "GOOGLE_CLOUD_PROJECT and PAIRPILOT_CANDIDATE_BASE_URL are required"
        )
    if CONFIRMATION != "SEED_ISOLATED_V2_CANDIDATE":
        raise RuntimeError("exact PAIRPILOT_COHORT_CONFIRM is required")
    if "candidate" not in BASE_URL:
        raise RuntimeError("candidate URL must contain the candidate tag")
    response: requests.Response | None = None
    for attempt in range(4):
        try:
            response = requests.get(BASE_URL + "/api/health", timeout=45)
            break
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 3:
                raise
            time.sleep(2**attempt)
    if response is None:  # pragma: no cover - defensive assertion
        raise RuntimeError("candidate health check did not produce a response")
    response.raise_for_status()
    health = response.json()
    if health.get("environment") != "candidate":
        raise RuntimeError("target did not report environment=candidate")


async def _ensure_communities() -> None:
    store = GoogleCloudStore(
        project_id=PROJECT,
        topic_id=EVENT_TOPIC,
        collection_prefix=COLLECTION_PREFIX,
        environment="candidate",
    )
    timestamp = datetime.now(UTC)
    for definition in COMMUNITIES:
        await store.create(
            "communities",
            str(definition["community_id"]),
            {
                "schema_version": 4,
                "namespace": "candidate",
                **definition,
                "purpose": definition["description"],
                "status": "ACTIVE",
                "rules": [
                    "Share only minimum public task information.",
                    "No login email, private itinerary, or protected Memory.",
                    "Final commitments require both humans.",
                ],
                "created_at": timestamp,
                "updated_at": timestamp,
            },
        )


def _users(session: AuthorizedSession) -> list[ControlledUser]:
    return [
        ControlledUser(
            index=index,
            email=f"pairpilot-v2-controlled-{index:02d}@example.com",
            display_name=f"Controlled Candidate User {index:02d}",
            secret_id=f"pairpilot-v2-candidate-user-{index:02d}-password",
            password=_secret_password(
                session, f"pairpilot-v2-candidate-user-{index:02d}-password"
            ),
        )
        for index in range(1, 11)
    ]


def _provision(user: ControlledUser, api_key: str) -> None:
    try:
        record = auth.get_user_by_email(user.email)
        record = auth.update_user(
            record.uid,
            password=user.password,
            email_verified=True,
            display_name=user.display_name,
            disabled=False,
        )
    except auth.UserNotFoundError:
        record = auth.create_user(
            email=user.email,
            password=user.password,
            email_verified=True,
            display_name=user.display_name,
        )
    user.uid = record.uid
    user.token = _sign_in(user.email, user.password, api_key)
    _api(user, "POST", "/api/app/provision", {}, retry_transport=True)
    _api(
        user,
        "PUT",
        "/api/app/onboarding",
        {
            "display_name": user.display_name,
            "timezone": "Europe/London",
            "general_location": "London, United Kingdom",
            "language": "English",
            "adult_confirmed": True,
            "public_profile_visible": True,
            "default_autonomy_mode": "COPILOT",
            "public_sharing_policy": "Ask before publishing public Posts.",
            "agent_sharing_policy": "Share minimum task-scoped evidence only.",
            "always_ask_policy": (
                "Always ask before protected disclosure or final commitment."
            ),
            "community_ids": [item["community_id"] for item in COMMUNITIES],
            "default_public_visibility": "COMMUNITY",
            "default_agent_visibility": "MINIMUM_NECESSARY",
            "notification_preference": "IN_APP",
        },
        retry_transport=True,
    )
    for community in COMMUNITIES:
        _api(
            user,
            "POST",
            f"/api/app/communities/{community['community_id']}/join",
            {},
            retry_transport=True,
        )


def _task_spec(index: int, *, generation: str = "base") -> dict[str, Any]:
    task_type = TASK_TYPES[index % len(TASK_TYPES)]
    community = COMMUNITIES[(index // 5) % len(COMMUNITIES)]
    type_label = task_type.replace("_", " ").title()
    requirements = {
        "ROOM_SHARE": ["non-smoking", "quiet overnight", "individual expenses"],
        "MEAL_COMPANION": ["60–90 minutes", "individual expenses", "public venue"],
        "COFFEE_CHAT": ["AI builders", "focused conversation", "public venue"],
        "EVENT_BUDDY": ["full event day", "flexible pace", "individual expenses"],
        "HACKATHON_TEAMMATE": ["available both days", "collaborative", "ships a demo"],
    }[task_type]
    location = str(community["location"])
    title_prefix = "" if generation == "base" else f"Acceptance {generation} · "
    return {
        "title": f"{title_prefix}{type_label} option {index + 1:02d}",
        "task_type": task_type,
        "goal": (
            f"Find a reliable adult participant for {type_label.lower()} in "
            f"{location}; "
            "coordinate concrete terms through our Personal Agents."
        ),
        "event": str(community["name"]).split(" ·", 1)[0],
        "location": location,
        "date_start": "2026-10-15",
        "date_end": "2026-10-17",
        "public_requirements": requirements,
        "maximum_additional_cost_usd": 120,
        "partial_date_overlap_allowed": True,
        "community_id": community["community_id"],
    }


def _close_active_controlled_tasks(users: list[ControlledUser]) -> int:
    """Release quota through the product API before a repeat acceptance run."""

    closed = 0
    terminal_statuses = {"COMPLETED", "CANCELLED", "CLOSED"}
    for user in users:
        state = _api(user, "GET", "/api/app/bootstrap", retry_transport=True)
        for task in state["tasks"]:
            if str(task.get("status") or "").upper() in terminal_statuses:
                continue
            _api(
                user,
                "POST",
                f"/api/app/tasks/{task['task_id']}/close",
                {},
                retry_transport=True,
            )
            closed += 1
    return closed


def _seed_posts(
    users: list[ControlledUser], *, generation: str = "base"
) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    state_by_user = {
        user.index: _api(user, "GET", "/api/app/bootstrap", retry_transport=True)
        for user in users
    }
    for index in range(25):
        user = users[index % len(users)]
        spec = _task_spec(index, generation=generation)
        state = state_by_user[user.index]
        task = next(
            (item for item in state["tasks"] if item.get("title") == spec["title"]),
            None,
        )
        if task is None:
            task = _api(user, "POST", "/api/app/tasks", spec)["task"]
            state["tasks"].append(task)
        published_post = next(
            (
                item
                for item in state["myPosts"]
                if item.get("task_id") == task["task_id"]
            ),
            None,
        )
        if published_post is None:
            published = _api(
                user,
                "POST",
                f"/api/app/tasks/{task['task_id']}/publish",
                {
                    "public_title": spec["title"],
                    "public_summary": spec["goal"],
                    "public_requirements": spec["public_requirements"],
                },
                retry_transport=True,
            )
            published_post = published.get("post", {})
            state["myPosts"].append(published_post)
        posts.append(
            {
                "owner_index": user.index,
                "task_id": task["task_id"],
                "intent_id": task["intent_id"],
                "task_type": spec["task_type"],
                "community_id": spec["community_id"],
                "status": published_post.get("status", "OPEN"),
            }
        )
    return posts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", action="store_true")
    parser.add_argument(
        "--generation",
        default="base",
        help="bounded cohort generation label used to create fresh deterministic tasks",
    )
    parser.add_argument(
        "--replenish",
        action="store_true",
        help="close active controlled-user tasks through the product API first",
    )
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{1,24}", args.generation):
        parser.error("--generation must match [a-z0-9-]{1,24}")
    if args.replenish and args.generation == "base":
        parser.error("--replenish requires a non-base --generation")
    plan = {
        "users": 10,
        "communities": [item["name"] for item in COMMUNITIES],
        "posts": 25,
        "task_types": list(TASK_TYPES),
        "credentials": "Secret Manager only",
        "outcomes_hardcoded": False,
        "generation": args.generation,
    }
    if args.plan:
        print(json.dumps(plan, indent=2))
        return
    _assert_candidate_target()
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": PROJECT})
    session = _admin_session()
    asyncio.run(_ensure_communities())
    api_key = _firebase_api_key(session)
    users = _users(session)
    for user in users:
        _provision(user, api_key)
        print(f"provisioned controlled user {user.index:02d}/10", file=sys.stderr)
    closed_tasks = _close_active_controlled_tasks(users) if args.replenish else 0
    posts = _seed_posts(users, generation=args.generation)
    print(
        json.dumps(
            {
                **plan,
                "status": "SEEDED",
                "candidate_url": BASE_URL,
                "user_uids": [user.uid for user in users],
                "secret_ids": [user.secret_id for user in users],
                "posts": posts,
                "closed_tasks": closed_tasks,
                "passwords_printed": False,
                "tokens_printed": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
