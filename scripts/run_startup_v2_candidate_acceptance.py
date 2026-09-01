"""Run bounded Startup V2 acceptance against the isolated candidate cohort.

The driver discovers seeded objects from authoritative APIs. It does not inject
candidate assessments, Agent messages, proposals, approvals, Matches, or
relationship outcomes. Those are created only through generic product routes.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Make both the application packages and the sibling seeder importable when the
# driver is launched directly from a clean checkout.
REPO_ROOT = Path(__file__).resolve().parents[1]
for source_root in (
    REPO_ROOT / "packages" / "schemas",
    REPO_ROOT / "services" / "orchestrator",
    REPO_ROOT / "services" / "peer_agents",
    REPO_ROOT / "scripts",
):
    sys.path.insert(0, str(source_root))

import firebase_admin  # noqa: E402
import requests  # noqa: E402
from pairpilot_orchestrator.infrastructure.google_cloud import (  # noqa: E402
    GoogleCloudStore,
)
from pairpilot_orchestrator.multi_user_platform import stable_id  # noqa: E402
from seed_startup_v2_candidate_cohort import (  # noqa: E402
    BASE_URL,
    COLLECTION_PREFIX,
    EVENT_TOPIC,
    PROJECT,
    ControlledUser,
    _admin_session,
    _api,
    _assert_candidate_target,
    _firebase_api_key,
    _secret_password,
    _sign_in,
)


def _users(api_key: str) -> list[ControlledUser]:
    session = _admin_session()
    users: list[ControlledUser] = []
    for index in range(1, 11):
        secret_id = f"pairpilot-v2-candidate-user-{index:02d}-password"
        password = _secret_password(session, secret_id)
        user = ControlledUser(
            index=index,
            email=f"pairpilot-v2-controlled-{index:02d}@example.com",
            display_name=f"Controlled Candidate User {index:02d}",
            secret_id=secret_id,
            password=password,
            token=_sign_in(
                f"pairpilot-v2-controlled-{index:02d}@example.com",
                password,
                api_key,
            ),
        )
        profile = _api(user, "GET", "/api/app/bootstrap")["profile"]
        user.uid = str(profile["uid"])
        users.append(user)
    return users


def _states(users: list[ControlledUser]) -> dict[int, dict[str, Any]]:
    return {user.index: _api(user, "GET", "/api/app/bootstrap") for user in users}


def _cohort_inventory(states: dict[int, dict[str, Any]]) -> dict[str, Any]:
    task_ids: set[str] = set()
    post_ids: set[str] = set()
    task_types: set[str] = set()
    community_ids: set[str] = set()
    for state in states.values():
        for task in state["tasks"]:
            task_ids.add(str(task["task_id"]))
            task_types.add(str(task["task_type"]))
            community_ids.add(str(task["community_id"]))
        post_ids.update(str(post["intent_id"]) for post in state["myPosts"])
    if len(task_ids) < 25 or len(post_ids) < 25:
        raise RuntimeError("candidate cohort does not contain 25 Requests and Posts")
    if len(task_types) < 5 or len(community_ids) < 3:
        raise RuntimeError(
            "candidate cohort lacks required task or Community diversity"
        )
    return {
        "users": len(states),
        "tasks": len(task_ids),
        "posts": len(post_ids),
        "task_types": sorted(task_types),
        "communities": sorted(community_ids),
    }


def _pair_candidates(
    users: list[ControlledUser], states: dict[int, dict[str, Any]]
) -> list[tuple[ControlledUser, dict[str, Any], ControlledUser, dict[str, Any]]]:
    by_key: dict[tuple[str, str], list[tuple[ControlledUser, dict[str, Any]]]] = {}
    for user in users:
        for task in states[user.index]["tasks"]:
            post = next(
                (
                    item
                    for item in states[user.index]["myPosts"]
                    if item.get("task_id") == task["task_id"]
                    and item.get("status") == "OPEN"
                ),
                None,
            )
            if post is None:
                continue
            key = (str(task["task_type"]), str(task["community_id"]))
            by_key.setdefault(key, []).append((user, {**task, **post}))
    pairs = []
    for candidates in by_key.values():
        if len(candidates) < 2:
            continue
        owner, own = candidates[0]
        peer, peer_post = next(
            (item for item in candidates[1:] if item[0].uid != owner.uid),
            (None, None),
        )
        if peer is not None and peer_post is not None:
            pairs.append((owner, own, peer, peer_post))
    if len(pairs) < 8:
        raise RuntimeError(f"only {len(pairs)} compatible cohort pairs were found")
    return pairs[:8]


def _wait_for_assessment(
    owner: ControlledUser, task_id: str, candidate_intent_id: str
) -> dict[str, Any]:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        state = _api(owner, "GET", "/api/app/bootstrap")
        assessment = next(
            (
                item
                for item in state["candidateAssessments"]
                if item.get("task_id") == task_id
                and item.get("candidate_intent_id") == candidate_intent_id
            ),
            None,
        )
        if assessment and (
            assessment.get("room_id") or assessment.get("active_room_id")
        ):
            return dict(assessment)
        time.sleep(4)
    raise RuntimeError("Agent contact did not produce a candidate Room in time")


def _contact_pairs(
    pairs: list[tuple[ControlledUser, dict[str, Any], ControlledUser, dict[str, Any]]],
) -> list[dict[str, Any]]:
    assessments: list[dict[str, Any]] = []
    for owner, own, _peer, peer_post in pairs:
        task_id = str(own["task_id"])
        candidate_intent_id = str(peer_post["intent_id"])
        state = _api(owner, "GET", "/api/app/bootstrap")
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
        assessments.append(_wait_for_assessment(owner, task_id, candidate_intent_id))
    return assessments


def _approve_plan(
    owner: ControlledUser,
    peer: ControlledUser,
    task_id: str,
    assessment: dict[str, Any],
) -> dict[str, Any]:
    proposal_id = str(assessment.get("proposal_id") or "")
    if not proposal_id:
        proposal = _api(
            owner,
            "POST",
            f"/api/app/tasks/{task_id}/candidates/"
            f"{assessment['candidate_intent_id']}/proposal",
            {},
        )["proposal"]
        proposal_id = str(proposal["proposal_id"])
        version = int(proposal["version"])
    else:
        decisions = _api(owner, "GET", "/api/app/decisions")["open"]
        decision = next(
            item for item in decisions if item.get("proposal_id") == proposal_id
        )
        version = int(decision.get("proposal_version") or decision.get("version"))
    approval = {
        "proposal_version": version,
        "confirmation": f"APPROVE VERSION {version}",
    }
    first = _api(owner, "POST", f"/api/app/proposals/{proposal_id}/approve", approval)
    second = _api(peer, "POST", f"/api/app/proposals/{proposal_id}/approve", approval)
    if second.get("status") != "MATCH_COMMITTED":
        raise RuntimeError("dual approval did not commit a Match")
    state = _api(owner, "GET", "/api/app/bootstrap")
    match = next(
        item for item in state["matches"] if item["proposal_id"] == proposal_id
    )
    return {
        "proposal_id": proposal_id,
        "version": version,
        "first_status": first["status"],
        "second_status": second["status"],
        "match_id": match["match_id"],
    }


def _complete_or_cancel(
    plans: list[dict[str, Any]],
    pairs: list[tuple[ControlledUser, dict[str, Any], ControlledUser, dict[str, Any]]],
) -> dict[str, list[str]]:
    completed: list[str] = []
    cancelled: list[str] = []
    for index, plan in enumerate(plans):
        owner = pairs[index][0]
        match_id = str(plan["match_id"])
        if index < 4:
            _api(
                owner,
                "POST",
                f"/api/app/matches/{match_id}/complete",
                {"confirmation": "MARK PLAN COMPLETED"},
            )
            completed.append(match_id)
        else:
            _api(
                owner,
                "POST",
                f"/api/app/matches/{match_id}/cancel",
                {
                    "reason": "Controlled candidate cancellation recovery scenario",
                    "reopen_candidate_pool": True,
                },
            )
            cancelled.append(match_id)
    return {"completed": completed, "cancelled": cancelled}


async def _seed_memory_volume(users: list[ControlledUser]) -> list[str]:
    store = GoogleCloudStore(
        project_id=PROJECT,
        topic_id=EVENT_TOPIC,
        collection_prefix=COLLECTION_PREFIX,
    )
    statuses = ("PROPOSED", "CONFIRMED", "REJECTED", "ARCHIVED")
    memory_types = (
        "CONFIRMED_USER_MEMORY",
        "TASK_MEMORY",
        "EPISODIC_MEMORY",
        "RELATIONAL_MEMORY",
        "WORKING_BELIEF",
    )
    ids: list[str] = []
    for index in range(20):
        owner = users[index % len(users)]
        memory_id = stable_id("memory", "candidate-cohort", str(index))
        await store.create(
            "memories",
            memory_id,
            {
                "schema_version": 4,
                "namespace": "candidate",
                "memory_id": memory_id,
                "owner_uid": owner.uid,
                "content": f"Controlled cohort preference {index + 1:02d}",
                "memory_type": memory_types[index % len(memory_types)],
                "status": statuses[index % len(statuses)],
                "scope": "EVENT_BUDDY" if index % 2 else "GLOBAL",
                "sensitivity": "LOW",
                "use_for_matching": statuses[index % len(statuses)] == "CONFIRMED",
                "provenance": {
                    "source": "CONTROLLED_CANDIDATE_COHORT_SETUP",
                    "not_a_runtime_outcome": True,
                },
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            },
        )
        ids.append(memory_id)
    return ids


def _security_gate(
    users: list[ControlledUser], states: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    user_a, user_b = users[0], users[1]
    task_b = str(states[user_b.index]["tasks"][0]["task_id"])
    idor = requests.get(
        BASE_URL + f"/api/app/tasks/{task_b}",
        headers={"Authorization": f"Bearer {user_a.token}"},
        timeout=30,
    )
    if idor.status_code != 403:
        raise RuntimeError(f"cross-user private task returned {idor.status_code}")
    legacy = requests.get(BASE_URL + "/api/os/bootstrap", timeout=30)
    if legacy.status_code != 404:
        raise RuntimeError("candidate exposed the legacy public OS surface")
    search = _api(
        user_a,
        "POST",
        "/api/app/explore/search",
        {"query": "reliable participant", "view": "LATEST", "limit": 30},
    )
    serialized = json.dumps(search)
    if "@example.com" in serialized or "owner_uid" in serialized:
        raise RuntimeError("Explore leaked an authentication or ownership field")
    return {
        "cross_user_task_status": idor.status_code,
        "legacy_surface_status": legacy.status_code,
        "explore_private_field_leak": False,
    }


def _non_model_load(
    users: list[ControlledUser], requests_count: int = 80
) -> dict[str, Any]:
    started = time.monotonic()

    def load(index: int) -> int:
        user = users[index % len(users)]
        response = requests.get(
            BASE_URL + "/api/app/bootstrap",
            headers={"Authorization": f"Bearer {user.token}"},
            timeout=40,
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=20) as executor:
        statuses = list(executor.map(load, range(requests_count)))
    failures = [status for status in statuses if status != 200]
    if failures:
        raise RuntimeError(f"authenticated load smoke had {len(failures)} failures")
    return {
        "requests": requests_count,
        "concurrency": 20,
        "failures": 0,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-agent-flows", action="store_true")
    args = parser.parse_args()
    _assert_candidate_target()
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": PROJECT})
    users = _users(_firebase_api_key(_admin_session()))
    states = _states(users)
    report: dict[str, Any] = {
        "run_id": f"v2-acceptance-{int(time.time())}",
        "candidate_url": BASE_URL,
        "inventory": _cohort_inventory(states),
        "security": _security_gate(users, states),
        "load": _non_model_load(users),
        "passwords_printed": False,
        "tokens_printed": False,
    }
    report["memory_volume"] = len(asyncio.run(_seed_memory_volume(users)))
    if not args.skip_agent_flows:
        pairs = _pair_candidates(users, states)
        assessments = _contact_pairs(pairs)
        plans = [
            _approve_plan(owner, peer, str(own["task_id"]), assessments[index])
            for index, (owner, own, peer, _peer_post) in enumerate(pairs[:7])
        ]
        outcomes = _complete_or_cancel(plans, pairs)
        report["agent_flows"] = {
            "rooms": len(assessments),
            "matches": len(plans),
            **outcomes,
        }
    print(json.dumps({"status": "PASS", **report}, indent=2))


if __name__ == "__main__":
    main()
