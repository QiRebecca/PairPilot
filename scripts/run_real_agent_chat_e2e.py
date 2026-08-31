"""Exercise the real conversational two-user path without printing credentials."""

from __future__ import annotations

import json
import time
from datetime import date, timedelta
from typing import Any

import requests
from run_real_multi_user_e2e import (
    ACCOUNTS,
    BASE,
    _admin_session,
    _firebase_api_key,
    _sign_in,
)


class RealUser:
    def __init__(self, label: str, token: str) -> None:
        self.label = label
        self.token = token

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def call(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> dict[str, Any]:
        response = requests.request(
            method,
            BASE + path,
            headers=self.headers,
            json=body,
            timeout=45,
        )
        if response.status_code not in expected:
            raise RuntimeError(
                f"{self.label} {method} {path}: HTTP {response.status_code}"
            )
        return dict(response.json())

    def chat(
        self,
        conversation_id: str,
        content: str,
        *,
        task_id: str | None = None,
    ) -> list[dict[str, Any]]:
        client_message_id = f"e2e-{self.label.lower()}-{time.time_ns()}"
        encoded_conversation_id = requests.utils.quote(conversation_id, safe="")
        response = requests.post(
            BASE + f"/api/v1/conversations/{encoded_conversation_id}/messages",
            headers={**self.headers, "Accept": "text/event-stream"},
            json={
                "content": content,
                "client_message_id": client_message_id,
                "task_id": task_id,
            },
            stream=True,
            timeout=150,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"{self.label} chat {conversation_id}: HTTP {response.status_code}"
            )
        events: list[dict[str, Any]] = []
        event_name = ""
        data_lines: list[str] = []
        for raw_line in response.iter_lines(decode_unicode=True):
            line = raw_line or ""
            if not line:
                if event_name and data_lines:
                    payload = dict(json.loads("\n".join(data_lines)))
                    events.append({**payload, "type": event_name})
                event_name = ""
                data_lines = []
                continue
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())
        event_types = {str(item["type"]) for item in events}
        if "agent.error" in event_types or "agent.completed" not in event_types:
            raise RuntimeError(
                f"{self.label} Agent turn failed with events {sorted(event_types)}"
            )
        return events


def _tool_names(events: list[dict[str, Any]]) -> set[str]:
    return {
        str(item.get("tool_name"))
        for item in events
        if item.get("type") == "tool.started"
    }


def _onboard(user: RealUser) -> dict[str, Any]:
    user.call("POST", "/api/app/provision", {})
    user.call(
        "PUT",
        "/api/app/onboarding",
        {
            "display_name": f"Agent Chat Test {user.label}",
            "timezone": "Asia/Shanghai",
            "general_location": "Shanghai, China",
            "language": "en",
            "adult_confirmed": True,
            "public_profile_visible": True,
            "default_autonomy_mode": "COPILOT",
            "public_sharing_policy": "Ask before publishing.",
            "agent_sharing_policy": "Share minimum public task evidence only.",
            "always_ask_policy": (
                "Always ask before publication, disclosure, payment, booking, "
                "or commitment."
            ),
        },
    )
    return user.call("GET", "/api/app/bootstrap")


def main() -> None:
    admin = _admin_session()
    api_key = _firebase_api_key(admin)
    users = {
        label: RealUser(label, _sign_in(admin, api_key, uid, secret_id))
        for label, (uid, secret_id) in ACCOUNTS.items()
    }
    baselines = {label: _onboard(user) for label, user in users.items()}
    baseline_task_ids = {
        label: {str(item["task_id"]) for item in bootstrap["tasks"]}
        for label, bootstrap in baselines.items()
    }
    run_suffix = str(int(time.time()))
    start = (date.today() + timedelta(days=45)).isoformat()
    end = (date.today() + timedelta(days=48)).isoformat()
    event_name = f"Agent Chat Summit {run_suffix}"
    global_conversations = {
        label: next(
            str(item["conversation_id"])
            for item in bootstrap["conversations"]
            if item.get("kind") == "GLOBAL_PERSONAL_AGENT"
        )
        for label, bootstrap in baselines.items()
    }
    create_events: dict[str, list[dict[str, Any]]] = {}
    tasks: dict[str, dict[str, Any]] = {}
    for label, user in users.items():
        create_events[label] = user.chat(
            global_conversations[label],
            (
                f"Create a private request titled Chat E2E {label} {run_suffix}. "
                f"Goal: find one compatible adult non-smoking roommate for "
                f"{event_name} in Seoul from {start} through {end}. Public "
                "requirements are adult conference attendee and non-smoking. "
                "Maximum additional cost is 50 USD and partial dates are allowed. "
                "Do not publish anything. Use the task-creation tool and report only "
                "after it succeeds."
            ),
        )
        if "create_task_workspace" not in _tool_names(create_events[label]):
            raise RuntimeError(f"{label} did not use create_task_workspace")
        bootstrap = user.call("GET", "/api/app/bootstrap")
        new_tasks = [
            dict(item)
            for item in bootstrap["tasks"]
            if str(item["task_id"]) not in baseline_task_ids[label]
        ]
        if len(new_tasks) != 1:
            raise RuntimeError(f"{label} created {len(new_tasks)} new tasks")
        tasks[label] = new_tasks[0]
        follow_up = user.chat(
            global_conversations[label],
            "What private request did you just create? Answer from our persistent "
            "context without creating another task.",
        )
        if "agent.completed" not in {str(item["type"]) for item in follow_up}:
            raise RuntimeError(f"{label} persistent follow-up failed")

    for label, user in users.items():
        task = tasks[label]
        task_conversation = str(task["conversation_id"])
        draft_events = user.chat(
            task_conversation,
            (
                f"Draft a public post titled {event_name} roommate {label}. The "
                "public summary should say I am looking to coordinate a shared room "
                "near the summit venue. Requirements: adult conference attendee and "
                "non-smoking. Use the draft tool. Do not publish yet."
            ),
            task_id=str(task["task_id"]),
        )
        if "draft_intent_post" not in _tool_names(draft_events):
            raise RuntimeError(f"{label} did not use draft_intent_post")
        publish_events = user.chat(
            task_conversation,
            (
                "PUBLISH THIS POST. Publish the current reviewed public draft now. "
                "Use only the title, summary, and public requirements already in the "
                "draft; do not disclose private conversation content."
            ),
            task_id=str(task["task_id"]),
        )
        if "publish_intent_post" not in _tool_names(publish_events):
            raise RuntimeError(f"{label} did not use publish_intent_post")

    decisions: dict[str, list[dict[str, Any]]] = {}
    finals: dict[str, dict[str, Any]] = {}
    for _attempt in range(40):
        for label, user in users.items():
            finals[label] = user.call("GET", "/api/app/bootstrap")
            decisions[label] = [
                dict(item)
                for item in finals[label]["decisions"]
                if item.get("type") == "APPROVE_PROPOSAL"
                and item.get("status") == "OPEN"
                and item.get("task_id") == tasks[label]["task_id"]
            ]
        if decisions.get("A") and decisions.get("B"):
            break
        time.sleep(5)
    else:
        raise RuntimeError("persistent A2A decisions did not arrive in 200 seconds")

    proposal_id = str(decisions["A"][0]["proposal_id"])
    version = int(decisions["A"][0]["proposal_version"])
    if decisions["B"][0]["proposal_id"] != proposal_id:
        raise RuntimeError("users received different proposals")
    approval = {
        "proposal_version": version,
        "confirmation": f"APPROVE VERSION {version}",
    }
    first = users["A"].call(
        "POST", f"/api/app/proposals/{proposal_id}/approve", approval
    )
    second = users["B"].call(
        "POST", f"/api/app/proposals/{proposal_id}/approve", approval
    )
    if first["status"] != "WAITING_FOR_OTHER_HUMAN":
        raise RuntimeError("first approval incorrectly committed the match")
    if second["status"] != "MATCH_COMMITTED":
        raise RuntimeError("second approval did not commit the match")

    audits: dict[str, dict[str, Any]] = {}
    for label, user in users.items():
        task = tasks[label]
        audits[label] = user.call(
            "GET",
            "/api/v1/conversations/"
            + requests.utils.quote(str(task["conversation_id"]), safe="")
            + "/audit",
        )
        assistants = [
            item
            for item in audits[label]["messages"]
            if item.get("role") == "PERSONAL_AGENT"
        ]
        if not assistants or not all(
            item.get("message_classification") == "FRESH_LIVE_GEMINI_RESPONSE"
            and item.get("model_id") == "gemini-3.7-flash"
            and item.get("adk_session_id")
            and item.get("adk_invocation_id")
            for item in assistants
        ):
            raise RuntimeError(f"{label} assistant provenance is incomplete")
        if not audits[label]["a2aTurns"] or not all(
            item.get("status") == "COMPLETED"
            and item.get("adk_session_id")
            and item.get("model_id") == "gemini-3.7-flash"
            for item in audits[label]["a2aTurns"]
        ):
            raise RuntimeError(f"{label} persistent A2A provenance is incomplete")

    idor = requests.get(
        BASE
        + "/api/v1/conversations/"
        + requests.utils.quote(str(tasks["B"]["conversation_id"]), safe="")
        + "/audit",
        headers=users["A"].headers,
        timeout=30,
    )
    if idor.status_code != 403:
        raise RuntimeError(f"cross-user conversation audit returned {idor.status_code}")

    print(
        json.dumps(
            {
                "status": "PASS",
                "candidate": BASE,
                "testUserUids": {
                    label: finals[label]["profile"]["uid"] for label in users
                },
                "agentIdsDistinct": (
                    finals["A"]["personalAgent"]["agent_id"]
                    != finals["B"]["personalAgent"]["agent_id"]
                ),
                "globalConversationIds": global_conversations,
                "taskConversationIds": {
                    label: tasks[label]["conversation_id"] for label in users
                },
                "createTools": {
                    label: sorted(_tool_names(create_events[label])) for label in users
                },
                "persistentTaskA2ATurnCounts": {
                    label: len(audits[label]["a2aTurns"]) for label in users
                },
                "proposalId": proposal_id,
                "proposalVersion": version,
                "firstApproval": first["status"],
                "secondApproval": second["status"],
                "crossUserConversationAuditStatus": idor.status_code,
                "passwordsPrinted": False,
                "idTokensPrinted": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
