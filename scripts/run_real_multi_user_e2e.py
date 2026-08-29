"""Run the real Firebase two-user gate without exposing credentials or ID tokens."""

from __future__ import annotations

import base64
import json
import os
import time
from datetime import date, timedelta
from typing import Any

import google.auth
import requests
from google.auth.transport.requests import AuthorizedSession

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
BASE = os.environ["PAIRPILOT_E2E_BASE_URL"].rstrip("/")
ACCOUNTS = {
    "A": (
        "TH6daBdwmLQPeHA0noJVGpAnGC53",
        "pairpilot-e2e-a-password",
    ),
    "B": (
        "TUQWZjC3yOSxYQHePig3QzF7Mgj1",
        "pairpilot-e2e-b-password",
    ),
}


def _admin_session() -> AuthorizedSession:
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return AuthorizedSession(credentials)


def _firebase_api_key(admin: AuthorizedSession) -> str:
    apps = admin.get(
        f"https://firebase.googleapis.com/v1beta1/projects/{PROJECT}/webApps"
        "?pageSize=100"
    ).json()["apps"]
    app_id = next(
        item["appId"]
        for item in apps
        if item["displayName"] == "PairPilot Public Beta Web"
    )
    config = admin.get(
        f"https://firebase.googleapis.com/v1beta1/projects/{PROJECT}/webApps/"
        f"{app_id}/config"
    ).json()
    return str(config["apiKey"])


def _secret(admin: AuthorizedSession, secret_id: str) -> str:
    response = admin.get(
        f"https://secretmanager.googleapis.com/v1/projects/{PROJECT}/secrets/"
        f"{secret_id}/versions/latest:access"
    )
    response.raise_for_status()
    return base64.b64decode(response.json()["payload"]["data"]).decode()


def _email_for_uid(admin: AuthorizedSession, uid: str) -> str:
    response = admin.post(
        f"https://identitytoolkit.googleapis.com/v1/projects/{PROJECT}/accounts:lookup",
        json={"localId": [uid]},
    )
    response.raise_for_status()
    return str(response.json()["users"][0]["email"])


def _sign_in(admin: AuthorizedSession, api_key: str, uid: str, secret_id: str) -> str:
    response = requests.post(
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        f"?key={api_key}",
        json={
            "email": _email_for_uid(admin, uid),
            "password": _secret(admin, secret_id),
            "returnSecureToken": True,
        },
        timeout=20,
    )
    response.raise_for_status()
    return str(response.json()["idToken"])


def main() -> None:
    admin = _admin_session()
    api_key = _firebase_api_key(admin)
    tokens = {
        label: _sign_in(admin, api_key, uid, secret_id)
        for label, (uid, secret_id) in ACCOUNTS.items()
    }
    baseline_matches: dict[str, set[str]] = {}

    def call(
        label: str,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> dict[str, Any]:
        response = requests.request(
            method,
            BASE + path,
            headers={
                "Authorization": f"Bearer {tokens[label]}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=40,
        )
        if response.status_code not in expected:
            raise RuntimeError(f"{label} {method} {path}: HTTP {response.status_code}")
        return dict(response.json())

    for label in ("A", "B"):
        call(label, "POST", "/api/app/provision", {})
        call(
            label,
            "PUT",
            "/api/app/onboarding",
            {
                "display_name": f"Test User {label}",
                "timezone": "Asia/Shanghai",
                "general_location": "Shanghai, China",
                "language": "en",
                "adult_confirmed": True,
                "public_profile_visible": True,
                "default_autonomy_mode": "COPILOT",
                "public_sharing_policy": "Ask before publishing.",
                "agent_sharing_policy": ("Share only minimum public task evidence."),
                "always_ask_policy": (
                    "Always ask before publication, disclosure, payment, "
                    "booking, or commitment."
                ),
            },
        )
        baseline = call(label, "GET", "/api/app/bootstrap")
        baseline_matches[label] = {
            str(item["match_id"]) for item in baseline["matches"]
        }

    start = (date.today() + timedelta(days=30)).isoformat()
    end = (date.today() + timedelta(days=34)).isoformat()
    run_suffix = str(int(time.time()))
    tasks: dict[str, dict[str, Any]] = {}
    for label in ("A", "B"):
        tasks[label] = dict(
            call(
                label,
                "POST",
                "/api/app/tasks",
                {
                    "title": f"E2E ICML roommate {label} {run_suffix}",
                    "task_type": "conference_room_share",
                    "goal": (
                        "Find a compatible, non-smoking ICML roommate for Test "
                        f"User {label} while preserving private contact details."
                    ),
                    "event": f"ICML E2E {run_suffix}",
                    "location": "Seoul",
                    "date_start": start,
                    "date_end": end,
                    "public_requirements": ["ICML attendee", "non-smoking"],
                    "maximum_additional_cost_usd": 50,
                    "partial_date_overlap_allowed": True,
                },
            )["task"]
        )
        call(
            label,
            "POST",
            f"/api/app/tasks/{tasks[label]['task_id']}/publish",
            {
                "public_title": f"ICML E2E roommate request {label}",
                "public_summary": (
                    "Looking to coordinate a shared room near the conference venue."
                ),
                "public_requirements": ["ICML attendee", "non-smoking"],
            },
        )

    bootstraps: dict[str, dict[str, Any]] = {}
    decisions: dict[str, list[dict[str, Any]]] = {}
    for _attempt in range(36):
        for label in ("A", "B"):
            bootstraps[label] = call(label, "GET", "/api/app/bootstrap")
            decisions[label] = [
                dict(item)
                for item in bootstraps[label]["decisions"]
                if item.get("type") == "APPROVE_PROPOSAL"
                and item.get("status") == "OPEN"
                and item.get("task_id") == tasks[label]["task_id"]
            ]
        if decisions["A"] and decisions["B"]:
            break
        time.sleep(5)
    else:
        raise RuntimeError(
            "two separate proposal decisions did not arrive within 180 seconds"
        )

    proposal_id = str(decisions["A"][0]["proposal_id"])
    version = int(decisions["A"][0]["proposal_version"])
    assert decisions["B"][0]["proposal_id"] == proposal_id
    assert decisions["B"][0]["proposal_version"] == version
    approval = {
        "proposal_version": version,
        "confirmation": f"APPROVE VERSION {version}",
    }
    first = call("A", "POST", f"/api/app/proposals/{proposal_id}/approve", approval)
    assert first["status"] == "WAITING_FOR_OTHER_HUMAN"
    after_first = call("A", "GET", "/api/app/bootstrap")
    assert {
        str(item["match_id"]) for item in after_first["matches"]
    } == baseline_matches["A"]
    second = call("B", "POST", f"/api/app/proposals/{proposal_id}/approve", approval)
    assert second["status"] == "MATCH_COMMITTED"
    replay = call("B", "POST", f"/api/app/proposals/{proposal_id}/approve", approval)
    assert replay["status"] == "MATCH_COMMITTED"

    finals = {label: call(label, "GET", "/api/app/bootstrap") for label in ("A", "B")}
    for label in ("A", "B"):
        new_matches = [
            item
            for item in finals[label]["matches"]
            if item.get("proposal_id") == proposal_id
        ]
        assert len(new_matches) == 1
        assert len(finals[label]["relationships"]) >= 1
        own_post = next(
            item
            for item in finals[label]["myPosts"]
            if item.get("intent_id") == tasks[label]["intent_id"]
        )
        assert own_post["status"] == "MATCHED"
        assert "participant_uids" not in json.dumps(finals[label]["rooms"])
        assert "@" not in json.dumps(finals[label]["explorePosts"])
    assert tasks["A"]["task_id"] not in {
        item["task_id"] for item in finals["B"]["tasks"]
    }
    assert tasks["B"]["task_id"] not in {
        item["task_id"] for item in finals["A"]["tasks"]
    }
    idor = requests.get(
        BASE + f"/api/app/tasks/{tasks['B']['task_id']}",
        headers={"Authorization": f"Bearer {tokens['A']}"},
        timeout=20,
    )
    assert idor.status_code == 403
    matching_rooms = [
        item for item in finals["A"]["rooms"] if item.get("proposal_id") == proposal_id
    ]
    assert len(matching_rooms) == 1
    room_id = str(matching_rooms[0]["room_id"])
    for label in ("A", "B"):
        room = call(label, "GET", f"/api/app/rooms/{room_id}")["room"]
        assert room["human_participation_available"] is True

    print(
        json.dumps(
            {
                "status": "PASS",
                "testUserUids": {
                    label: finals[label]["profile"]["uid"] for label in ("A", "B")
                },
                "agentIds": {
                    label: finals[label]["personalAgent"]["agent_id"]
                    for label in ("A", "B")
                },
                "taskIds": {label: tasks[label]["task_id"] for label in ("A", "B")},
                "proposalId": proposal_id,
                "proposalVersion": version,
                "firstApproval": first["status"],
                "secondApproval": second["status"],
                "duplicateApproval": replay["status"],
                "matchId": next(
                    item["match_id"]
                    for item in finals["A"]["matches"]
                    if item.get("proposal_id") == proposal_id
                ),
                "roomId": room_id,
                "crossUserTaskReadStatus": idor.status_code,
                "passwordsPrinted": False,
                "idTokensPrinted": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
