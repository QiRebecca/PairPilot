"""Live multi-intent, multi-user, multi-Agent acceptance for PairPilot V1."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import firebase_admin
from v1_live_acceptance import (
    RUN_SUFFIX,
    TestUser,
    _request,
    api,
    bootstrap,
    create_or_update_user,
    onboard,
)


@dataclass(frozen=True)
class Scenario:
    intent_type: str
    label: str
    event: str
    location: str
    date_start: str
    date_end: str
    goal: str
    public_requirements: list[str]
    maximum_additional_cost_usd: int


SCENARIOS = (
    Scenario(
        intent_type="ROOM_SHARE",
        label="Build Week quiet room share",
        event="OpenAI Build Week",
        location="Seoul",
        date_start="2026-09-10",
        date_end="2026-09-12",
        goal="Find an adult Build Week attendee for a quiet hotel room share.",
        public_requirements=["Adult attendee", "Quiet nights"],
        maximum_additional_cost_usd=90,
    ),
    Scenario(
        intent_type="MEAL_COMPANION",
        label="Build Week dinner companion",
        event="Build Week community dinner",
        location="Seoul",
        date_start="2026-09-10",
        date_end="2026-09-10",
        goal="Find an adult attendee for a relaxed dinner after Build Week.",
        public_requirements=["Adult attendee", "Split personal orders"],
        maximum_additional_cost_usd=40,
    ),
    Scenario(
        intent_type="COFFEE_CHAT",
        label="Agent builders coffee chat",
        event="Agent builders coffee chat",
        location="Seoul",
        date_start="2026-09-11",
        date_end="2026-09-11",
        goal="Meet another adult agent builder for a focused coffee conversation.",
        public_requirements=["Adult builder", "Interested in agents"],
        maximum_additional_cost_usd=20,
    ),
    Scenario(
        intent_type="EVENT_BUDDY",
        label="Hong Kong Disneyland photo buddy",
        event="Hong Kong Disneyland visit",
        location="Hong Kong",
        date_start="2026-09-10",
        date_end="2026-09-10",
        goal="Find an adult woman to enjoy Disneyland rides and take photos together.",
        public_requirements=["Adult woman", "Enjoys photos", "Easygoing"],
        maximum_additional_cost_usd=0,
    ),
    Scenario(
        intent_type="HACKATHON_TEAMMATE",
        label="Agentic hackathon teammate",
        event="All Things Agentic Hackathon",
        location="Online and Seoul",
        date_start="2026-09-10",
        date_end="2026-09-12",
        goal="Find an adult teammate to build and present an agentic product.",
        public_requirements=["Adult builder", "Can ship a demo"],
        maximum_additional_cost_usd=50,
    ),
)


def chat(user: TestUser, content: str, turn_name: str) -> str:
    conversation_id = f"user:{user.uid}:global"
    status, payload = _request(
        "POST",
        (
            f"{__import__('v1_live_acceptance').BASE_URL}/api/v1/conversations/"
            f"{quote(conversation_id, safe='')}/messages"
        ),
        token=user.token,
        body={
            "content": content,
            "client_message_id": f"multi-{RUN_SUFFIX}-{user.index}-{turn_name}",
            "task_id": None,
            "retry_of": None,
        },
        timeout=240,
    )
    if status != 200 or not isinstance(payload, str):
        raise AssertionError(f"chat {turn_name} failed HTTP {status}: {payload}")
    if "event: agent.error" in payload or "event: agent.completed" not in payload:
        raise AssertionError(f"chat {turn_name} did not complete: {payload[-2000:]}")
    return payload


def create_owner_task_via_follow_up(user: TestUser, scenario: Scenario) -> None:
    chat(
        user,
        (
            f"I want help with a {scenario.label}. Do not create a task yet. "
            "Ask me briefly for the date, location and public requirements you need."
        ),
        "clarify",
    )
    before = {str(item["task_id"]) for item in bootstrap(user).get("tasks", [])}
    chat(
        user,
        (
            "Here are all details. Create the private task now as "
            f"{scenario.intent_type}; "
            f"do not publish it. Title: {scenario.label}. Goal: {scenario.goal} "
            f"Event: {scenario.event}. Location: {scenario.location}. "
            f"Dates: {scenario.date_start} through {scenario.date_end}. "
            f"Public requirements: {', '.join(scenario.public_requirements)}. "
            f"Maximum additional cost USD: {scenario.maximum_additional_cost_usd}. "
            "Partial date overlap is allowed."
        ),
        "create",
    )
    state = bootstrap(user)
    created = [
        item for item in state.get("tasks", []) if str(item["task_id"]) not in before
    ]
    if len(created) != 1:
        raise AssertionError(
            f"{scenario.intent_type} follow-up created {len(created)} tasks, expected 1"
        )
    task = created[0]
    if task.get("task_type") != scenario.intent_type:
        raise AssertionError(
            f"{scenario.intent_type} was classified as {task.get('task_type')}"
        )
    user.task_id = str(task["task_id"])
    user.intent_id = str(task["intent_id"])


def create_task_by_api(
    user: TestUser, scenario: Scenario, *, seed: bool = False
) -> None:
    marker = "seed" if seed else "peer"
    result = api(
        user,
        "POST",
        "/api/app/tasks",
        {
            "title": f"{scenario.label} {marker} {RUN_SUFFIX}",
            "task_type": scenario.intent_type,
            "goal": (
                f"{scenario.goal} Private canary PRIVATE-{RUN_SUFFIX}-{user.index} "
                "must never be shared."
            ),
            "event": scenario.event,
            "location": scenario.location,
            "date_start": scenario.date_start,
            "date_end": scenario.date_end,
            "public_requirements": scenario.public_requirements,
            "maximum_additional_cost_usd": scenario.maximum_additional_cost_usd,
            "partial_date_overlap_allowed": True,
            "community_id": "community_icml_seoul_2026",
        },
    )
    user.task_id = str(result["task"]["task_id"])
    user.intent_id = str(result["task"]["intent_id"])


def publish(user: TestUser, scenario: Scenario) -> None:
    api(
        user,
        "POST",
        f"/api/app/tasks/{user.task_id}/publish",
        {
            "public_title": f"{scenario.label} — test {RUN_SUFFIX}",
            "public_summary": scenario.goal,
            "public_requirements": scenario.public_requirements,
        },
    )


def wait_for_exact_candidate(
    owner: TestUser, peer: TestUser, *, timeout_seconds: int = 480
) -> tuple[dict[str, Any], dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    latest: dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = bootstrap(owner)
        candidate = next(
            (
                item
                for item in latest.get("candidateAssessments", [])
                if item.get("task_id") == owner.task_id
                and item.get("candidate_intent_id") == peer.intent_id
            ),
            None,
        )
        if candidate is not None:
            return latest, candidate
        time.sleep(10)
    raise AssertionError(
        f"candidate {peer.intent_id} was not discovered for {owner.task_id}: {latest}"
    )


def complete_match_flow(
    owner: TestUser,
    peer: TestUser,
    scenario: Scenario,
) -> dict[str, Any]:
    owner_state, candidate = wait_for_exact_candidate(owner, peer)
    if not owner_state.get("candidateRankEvents"):
        raise AssertionError(f"{scenario.intent_type} has no rank event")
    room_payload = api(owner, "GET", f"/api/app/rooms/{candidate['room_id']}")
    if len(room_payload.get("messages", [])) < 2:
        raise AssertionError(
            f"{scenario.intent_type} did not persist both Agent messages"
        )
    private_canary = f"PRIVATE-{RUN_SUFFIX}-{peer.index}"
    if private_canary in json.dumps(room_payload, ensure_ascii=False):
        raise AssertionError(f"{scenario.intent_type} leaked private task context")
    result = api(
        owner,
        "POST",
        (f"/api/app/tasks/{owner.task_id}/candidates/{peer.intent_id}/proposal"),
        {},
    )
    proposal = result["proposal"]
    for participant in (owner, peer):
        api(
            participant,
            "POST",
            f"/api/app/proposals/{proposal['proposal_id']}/approve",
            {
                "proposal_version": proposal["version"],
                "confirmation": f"APPROVE VERSION {proposal['version']}",
            },
        )
    matched = bootstrap(owner)
    match = next(
        item
        for item in matched["matches"]
        if item["match_id"] == proposal["proposal_id"]
    )
    api(
        owner,
        "PUT",
        f"/api/app/matches/{match['match_id']}/contacts/mine",
        {
            "wechat": f"pairpilot-{scenario.intent_type.lower()}-{RUN_SUFFIX}",
            "public_email": None,
            "phone": None,
            "whatsapp": None,
            "telegram": None,
            "linkedin": None,
            "other_handle": None,
        },
    )
    visible = api(peer, "GET", f"/api/app/matches/{match['match_id']}/contacts")
    if not visible.get("contactCards"):
        raise AssertionError(f"{scenario.intent_type} contact card was not visible")
    api(
        owner,
        "POST",
        f"/api/app/rooms/{match['room_id']}/messages",
        {
            "content": f"Matched {scenario.intent_type} live acceptance message.",
            "authorship": "HUMAN_WRITTEN",
            "idempotency_key": f"multi-{RUN_SUFFIX}-{scenario.intent_type}",
        },
    )
    state = bootstrap(owner)
    memory = next(
        item for item in state["memories"] if item.get("match_id") == match["match_id"]
    )
    api(
        owner,
        "POST",
        f"/api/app/memories/{memory['memory_id']}/actions",
        {"action": "CONFIRM"},
    )
    api(
        owner,
        "POST",
        f"/api/app/matches/{match['match_id']}/outcome",
        {
            "did_plan_happen": True,
            "would_coordinate_again": True,
            "agreed_term_inaccurate": False,
            "optional_feedback": f"Private {scenario.intent_type} acceptance feedback.",
        },
    )
    final_state = bootstrap(owner)
    if not final_state.get("notifications"):
        raise AssertionError(f"{scenario.intent_type} produced no notifications")
    return {
        "intent_type": scenario.intent_type,
        "match_id": match["match_id"],
        "candidate_room_id": candidate["room_id"],
        "shared_room_id": match["room_id"],
        "agent_messages": len(room_payload["messages"]),
    }


def create_open_seed_posts(start_index: int) -> list[TestUser]:
    seeds: list[TestUser] = []
    for offset, scenario in enumerate(SCENARIOS):
        seed = create_or_update_user(start_index + offset)
        onboard(seed)
        create_task_by_api(seed, scenario, seed=True)
        if offset == 0:
            status, _ = _request(
                "POST",
                (
                    f"{__import__('v1_live_acceptance').BASE_URL}/api/app/tasks/"
                    f"{seed.task_id}/publish"
                ),
                token=seed.token,
                body={
                    "public_title": "Unsafe test post",
                    "public_summary": "Contact me at unsafe@example.com in room 1204.",
                    "public_requirements": ["Call +1 555 0100"],
                },
            )
            if status < 400:
                raise AssertionError("sensitive public Post was accepted")
        publish(seed, scenario)
        seeds.append(seed)
    return seeds


def verify_safety_and_account_lifecycle(
    users: list[TestUser], seeds: list[TestUser]
) -> None:
    status, _ = _request(
        "GET",
        (
            f"{__import__('v1_live_acceptance').BASE_URL}/api/app/tasks/"
            f"{users[0].task_id}"
        ),
        token=users[2].token,
    )
    if status != 403:
        raise AssertionError(f"cross-user task read returned {status}, expected 403")
    api(
        users[0],
        "POST",
        "/api/app/reports",
        {
            "target_type": "POST",
            "target_id": seeds[-1].intent_id,
            "category": "OTHER",
            "details": "Multi-intent live acceptance moderation report.",
        },
    )
    target = next(
        item
        for item in bootstrap(users[0])["explorePosts"]
        if item["intent_id"] == seeds[-1].intent_id
    )
    api(
        users[0],
        "POST",
        "/api/app/blocks",
        {
            "target_agent_id": target["owner_agent_id"],
            "reason": "Multi-intent live acceptance block",
        },
    )
    disposable = create_or_update_user(99)
    onboard(disposable)
    exported = api(disposable, "GET", "/api/app/account/export")
    if not exported:
        raise AssertionError("account export was empty")
    api(
        disposable,
        "POST",
        "/api/app/account/delete",
        {"confirmation": "DELETE MY PAIRPILOT ACCOUNT"},
    )


def main() -> None:
    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            options={"projectId": __import__("os").environ["GOOGLE_CLOUD_PROJECT"]}
        )
    matched_users = [create_or_update_user(index) for index in range(1, 11)]
    for user in matched_users:
        onboard(user)
    for scenario_index, scenario in enumerate(SCENARIOS):
        owner = matched_users[scenario_index * 2]
        peer = matched_users[scenario_index * 2 + 1]
        create_owner_task_via_follow_up(owner, scenario)
        create_task_by_api(peer, scenario)
        before = [
            item
            for item in bootstrap(owner).get("candidateAssessments", [])
            if item.get("task_id") == owner.task_id
        ]
        if before:
            raise AssertionError(
                f"{scenario.intent_type} found a candidate before peer publication"
            )
        publish(owner, scenario)
        publish(peer, scenario)
    match_evidence = [
        complete_match_flow(
            matched_users[index * 2],
            matched_users[index * 2 + 1],
            scenario,
        )
        for index, scenario in enumerate(SCENARIOS)
    ]
    seeds = create_open_seed_posts(11)
    verify_safety_and_account_lifecycle(matched_users, seeds)
    evidence: dict[str, Any] = {
        "status": "PASS",
        "run_suffix": RUN_SUFFIX,
        "independent_users": 16,
        "persistent_chat_followups": len(SCENARIOS),
        "intent_types": [item.intent_type for item in SCENARIOS],
        "completed_matches": match_evidence,
        "open_seed_posts": [seed.intent_id for seed in seeds],
        "sensitive_public_post_rejected": True,
        "cross_user_task_read_status": 403,
        "report_block_export_delete_verified": True,
    }
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"V1 multi-intent live acceptance failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise
