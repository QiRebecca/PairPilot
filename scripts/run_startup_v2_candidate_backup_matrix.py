"""Exercise same-Request backup activation through candidate product APIs."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    REPO_ROOT / "packages" / "schemas",
    REPO_ROOT / "services" / "orchestrator",
    REPO_ROOT / "services" / "peer_agents",
    REPO_ROOT / "scripts",
):
    sys.path.insert(0, str(source_root))

from run_startup_v2_candidate_acceptance import (  # noqa: E402
    _approve_plan,
    _assert_candidate_target,
    _users,
    _wait_for_assessment,
)
from seed_startup_v2_candidate_cohort import (  # noqa: E402
    ControlledUser,
    _admin_session,
    _api,
    _firebase_api_key,
)

COMMUNITY_ID = "community_v2_university_orientation"
TASK_TYPE = "HACKATHON_TEAMMATE"


def _task_spec(title: str) -> dict[str, Any]:
    return {
        "title": title,
        "task_type": TASK_TYPE,
        "goal": (
            "Find a reliable adult production engineering teammate for a "
            "bounded acceptance exercise through our Personal Agents."
        ),
        "event": "University Orientation",
        "location": "Cambridge, United Kingdom",
        "date_start": "2026-10-15",
        "date_end": "2026-10-17",
        "public_requirements": [
            "available both days",
            "collaborative",
            "ships a demo",
        ],
        "maximum_additional_cost_usd": 120,
        "partial_date_overlap_allowed": True,
        "community_id": COMMUNITY_ID,
    }


def _ensure_open_post(user: ControlledUser, title: str) -> dict[str, Any]:
    state = _api(user, "GET", "/api/app/bootstrap", retry_transport=True)
    task = next((item for item in state["tasks"] if item.get("title") == title), None)
    if task is None:
        task = _api(user, "POST", "/api/app/tasks", _task_spec(title))["task"]
    post = next(
        (item for item in state["myPosts"] if item.get("task_id") == task["task_id"]),
        None,
    )
    if post is None:
        spec = _task_spec(title)
        post = _api(
            user,
            "POST",
            f"/api/app/tasks/{task['task_id']}/publish",
            {
                "public_title": title,
                "public_summary": spec["goal"],
                "public_requirements": spec["public_requirements"],
            },
            retry_transport=True,
        )["post"]
    elif post.get("status") != "OPEN":
        post = _api(
            user,
            "PATCH",
            f"/api/app/posts/{task['intent_id']}/status",
            {"status": "OPEN"},
        )["post"]
    return {**task, **post}


def _assessment(
    owner: ControlledUser, task_id: str, candidate_intent_id: str
) -> dict[str, Any]:
    state = _api(owner, "GET", "/api/app/bootstrap", retry_transport=True)
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
        _api(
            owner,
            "POST",
            f"/api/app/tasks/{task_id}/candidates/{candidate_intent_id}/contact",
            {},
        )
        return _wait_for_assessment(owner, task_id, candidate_intent_id)
    return existing


def _set_backup(
    owner: ControlledUser, task_id: str, candidate_intent_id: str
) -> dict[str, Any]:
    return _api(
        owner,
        "PATCH",
        f"/api/app/tasks/{task_id}/candidates/{candidate_intent_id}/state",
        {"state": "BACKUP"},
    )["candidate"]


def _unrelated_backup(owner: ControlledUser, owned_task_id: str) -> dict[str, Any]:
    state = _api(owner, "GET", "/api/app/bootstrap", retry_transport=True)
    candidate = next(
        (
            item
            for item in state["candidateAssessments"]
            if item.get("task_id") != owned_task_id
            and item.get("candidate_intent_id")
        ),
        None,
    )
    if candidate is None:
        raise RuntimeError("owner has no unrelated candidate for the isolation gate")
    return _set_backup(
        owner,
        str(candidate["task_id"]),
        str(candidate["candidate_intent_id"]),
    )


def main() -> None:
    _assert_candidate_target()
    users = _users(_firebase_api_key(_admin_session()))
    owner, primary_peer, backup_peer = users[4], users[5], users[6]
    owner_post = _ensure_open_post(owner, "Backup matrix owner request")
    primary_post = _ensure_open_post(primary_peer, "Backup matrix primary peer")
    backup_post = _ensure_open_post(backup_peer, "Backup matrix reserve peer")
    task_id = str(owner_post["task_id"])

    primary = _assessment(owner, task_id, str(primary_post["intent_id"]))
    reserve = _assessment(owner, task_id, str(backup_post["intent_id"]))
    _set_backup(owner, task_id, str(reserve["candidate_intent_id"]))
    unrelated = _unrelated_backup(owner, task_id)

    plan = _approve_plan(owner, primary_peer, task_id, primary)
    match_id = str(plan["match_id"])
    _api(
        owner,
        "POST",
        f"/api/app/matches/{match_id}/cancel",
        {
            "reason": "Controlled cancellation to verify same-Request backup routing.",
            "reopen_candidate_pool": False,
        },
    )
    activated = _api(
        owner,
        "POST",
        f"/api/app/matches/{match_id}/backup/activate",
        {},
    )
    selected = activated["candidate"]
    if selected.get("candidate_intent_id") != reserve.get("candidate_intent_id"):
        raise RuntimeError("backup activation crossed the owning Request boundary")
    if selected.get("state") != "CONTACTING":
        raise RuntimeError("same-Request backup did not enter CONTACTING")
    print(
        json.dumps(
            {
                "status": "PASS",
                "authenticated_users_exercised": 3,
                "real_agent_contacts": 2,
                "match_id": match_id,
                "cancelled": True,
                "same_request_task_id": task_id,
                "selected_backup_intent_id": selected["candidate_intent_id"],
                "unrelated_backup_task_id": unrelated["task_id"],
                "unrelated_backup_excluded": True,
                "passwords_printed": False,
                "tokens_printed": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
