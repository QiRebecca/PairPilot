"""Verify live Connection reuse and scoped Memory behavior through chat."""

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

from run_startup_v2_candidate_acceptance import (  # noqa: E402
    _assert_candidate_target,
    _stream_chat_turn,
    _users,
)
from seed_startup_v2_candidate_cohort import (  # noqa: E402
    ControlledUser,
    _admin_session,
    _api,
    _firebase_api_key,
)

COMMUNITY_ID = "community_v2_university_orientation"


def _ensure_task(
    user: ControlledUser, *, title: str, task_type: str
) -> dict[str, Any]:
    state = _api(user, "GET", "/api/app/bootstrap", retry_transport=True)
    existing = next(
        (item for item in state["tasks"] if item.get("title") == title), None
    )
    if existing is not None:
        return existing
    return _api(
        user,
        "POST",
        "/api/app/tasks",
        {
            "title": title,
            "task_type": task_type,
            "goal": (
                "Verify context-bounded Connection and Memory behavior with a "
                "real Personal Agent while retaining strict user control."
            ),
            "event": "University Orientation",
            "location": "Cambridge, United Kingdom",
            "date_start": "2026-10-15",
            "date_end": "2026-10-17",
            "public_requirements": ["public venue", "minimum necessary sharing"],
            "maximum_additional_cost_usd": 80,
            "partial_date_overlap_allowed": True,
            "community_id": COMMUNITY_ID,
        },
    )["task"]


def _tool_turn(
    user: ControlledUser, task: dict[str, Any], content: str, required: str
) -> dict[str, Any]:
    turn = _stream_chat_turn(
        user,
        conversation_id=str(task["conversation_id"]),
        task_id=str(task["task_id"]),
        content=content,
    )
    if required not in turn["tool_names"]:
        raise RuntimeError(f"live Personal Agent did not call {required}")
    return turn


def _memory_by_content(user: ControlledUser, content: str) -> dict[str, Any] | None:
    workspace = _api(user, "GET", "/api/app/memories", retry_transport=True)
    return next(
        (item for item in workspace["memories"] if item.get("content") == content),
        None,
    )


def _propose_memory(
    user: ControlledUser,
    task: dict[str, Any],
    *,
    content: str,
    scope: str,
    memory_type: str,
    topic_key: str,
) -> dict[str, Any]:
    memory = _memory_by_content(user, content)
    if memory is None:
        _tool_turn(
            user,
            task,
            (
                "Use propose_memory exactly once. Propose the exact content "
                f"'{content}' with scope '{scope}', memory_type '{memory_type}', "
                f"and topic_key '{topic_key}'. Do not confirm it yourself."
            ),
            "propose_memory",
        )
        memory = _memory_by_content(user, content)
    if memory is None:
        raise RuntimeError("Agent tool did not persist the proposed Memory")
    return memory


def _memory_detail(user: ControlledUser, memory_id: str) -> dict[str, Any]:
    return _api(user, "GET", f"/api/app/memories/{memory_id}")


def _confirm(user: ControlledUser, memory: dict[str, Any]) -> dict[str, Any]:
    if memory.get("status") == "CONFIRMED":
        return memory
    return _api(
        user,
        "POST",
        f"/api/app/memories/{memory['memory_id']}/actions",
        {"action": "CONFIRM"},
    )["memory"]


def main() -> None:
    _assert_candidate_target()
    users = _users(_firebase_api_key(_admin_session()))
    user = users[0]
    matching_task = _ensure_task(
        user,
        title="Context matrix room-share request",
        task_type="ROOM_SHARE",
    )
    mismatch_task = _ensure_task(
        user,
        title="Context matrix hackathon request",
        task_type="HACKATHON_TEAMMATE",
    )

    connections = _api(user, "GET", "/api/app/connections")["connections"]
    connection = next(
        (
            item
            for item in connections
            if "ROOM_SHARE" in set(item.get("task_contexts") or [])
        ),
        None,
    )
    if connection is None:
        raise RuntimeError("controlled user has no Room Share Connection")
    peer_agent_id = str(connection["personal_agent"]["agent_id"])
    _tool_turn(
        user,
        matching_task,
        (
            "For this Room Share Request, use request_warm_introduction with "
            f"peer_agent_id '{peer_agent_id}'. Check the authoritative prior "
            "Connection evidence and do not invent a new relationship."
        ),
        "request_warm_introduction",
    )
    _tool_turn(
        user,
        mismatch_task,
        (
            "For this Hackathon Teammate Request, use request_warm_introduction "
            f"with the same peer_agent_id '{peer_agent_id}'. Respect task-context "
            "compatibility and do not overgeneralize the old Room Share history."
        ),
        "request_warm_introduction",
    )
    detail = _api(
        user,
        "GET",
        f"/api/app/connections/{connection['connection_id']}",
    )
    usage = detail["usage_events"]
    matching_usage = next(
        (
            item
            for item in usage
            if item.get("task_id") == matching_task["task_id"]
            and item.get("purpose") == "INSPECT"
        ),
        None,
    )
    mismatch_usage = next(
        (
            item
            for item in usage
            if item.get("task_id") == mismatch_task["task_id"]
            and item.get("purpose") == "INSPECT"
        ),
        None,
    )
    if matching_usage is None or matching_usage.get("context_applicable") is not True:
        raise RuntimeError("Connection was not reusable in its supported task context")
    if mismatch_usage is None or mismatch_usage.get("context_applicable") is not False:
        raise RuntimeError("Connection history overgeneralized across task types")

    safe_suffix = uuid4().hex[:8].translate(
        str.maketrans("0123456789", "ghijklmnop")
    )
    scoped_content = (
        f"I prefer a quiet public planning environment ({safe_suffix})."
    )
    scoped = _propose_memory(
        user,
        matching_task,
        content=scoped_content,
        scope="ROOM_SHARE",
        memory_type="CONFIRMED_USER_MEMORY",
        topic_key="planning_environment",
    )
    scoped_id = str(scoped["memory_id"])
    before = _memory_detail(user, scoped_id)
    if scoped.get("status") == "PROPOSED" and before["usage_events"]:
        raise RuntimeError("proposed Memory affected context before confirmation")
    _confirm(user, scoped)
    _tool_turn(
        user,
        matching_task,
        (
            "Use inspect_memory with the query 'quiet public planning environment' "
            "and explain only the authoritative scoped result."
        ),
        "inspect_memory",
    )
    in_scope = _memory_detail(user, scoped_id)
    if not any(
        item.get("task_id") == matching_task["task_id"]
        for item in in_scope["usage_events"]
    ):
        raise RuntimeError("confirmed Memory was not used in its matching scope")
    _tool_turn(
        user,
        mismatch_task,
        (
            "Use inspect_memory with the query 'quiet public planning environment'. "
            "Do not use any Memory that is outside this Hackathon task scope."
        ),
        "inspect_memory",
    )
    out_of_scope = _memory_detail(user, scoped_id)
    if any(
        item.get("task_id") == mismatch_task["task_id"]
        for item in out_of_scope["usage_events"]
    ):
        raise RuntimeError("Memory leaked into an unrelated task scope")

    global_memory = _propose_memory(
        user,
        matching_task,
        content=f"I prefer early morning planning sessions ({safe_suffix}).",
        scope="GLOBAL",
        memory_type="CONFIRMED_USER_MEMORY",
        topic_key="planning_time",
    )
    task_memory = _propose_memory(
        user,
        matching_task,
        content=(
            "For this specific request I prefer afternoon planning sessions "
            f"({safe_suffix})."
        ),
        scope=f"TASK:{matching_task['task_id']}",
        memory_type="TASK_MEMORY",
        topic_key="planning_time",
    )
    _confirm(user, global_memory)
    _confirm(user, task_memory)
    _tool_turn(
        user,
        matching_task,
        (
            "Use inspect_memory with the query 'planning sessions'. Apply the "
            "task-specific exception instead of the global preference when both "
            "share the same topic_key."
        ),
        "inspect_memory",
    )
    global_detail = _memory_detail(user, str(global_memory["memory_id"]))
    task_detail = _memory_detail(user, str(task_memory["memory_id"]))
    if any(
        item.get("task_id") == matching_task["task_id"]
        for item in global_detail["usage_events"]
    ):
        raise RuntimeError("global Memory overrode a task-specific exception")
    if not any(
        item.get("task_id") == matching_task["task_id"]
        for item in task_detail["usage_events"]
    ):
        raise RuntimeError("task-specific Memory exception was not used")

    usage_count = len(_memory_detail(user, scoped_id)["usage_events"])
    _api(
        user,
        "POST",
        f"/api/app/memories/{scoped_id}/actions",
        {"action": "REJECT"},
    )
    _tool_turn(
        user,
        matching_task,
        (
            "Use inspect_memory with the query 'quiet public planning environment'. "
            "A rejected Memory must not be used."
        ),
        "inspect_memory",
    )
    rejected = _memory_detail(user, scoped_id)
    if len(rejected["usage_events"]) != usage_count:
        raise RuntimeError("rejected Memory continued to create usage events")

    print(
        json.dumps(
            {
                "status": "PASS",
                "authenticated_users_exercised": 1,
                "live_personal_agent_turns": 9,
                "connection_id": connection["connection_id"],
                "connection_context_applicable": True,
                "connection_context_mismatch": True,
                "proposed_memory_inert": True,
                "confirmed_memory_used_in_scope": True,
                "memory_out_of_scope_excluded": True,
                "why_this_was_used_visible": bool(in_scope["why_this_was_used"]),
                "task_exception_overrode_global": True,
                "rejected_memory_stopped": True,
                "passwords_printed": False,
                "tokens_printed": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
