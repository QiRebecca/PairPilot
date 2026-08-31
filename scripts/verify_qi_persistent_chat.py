"""Verify two consecutive live turns in Qi's one persistent task-focused chat."""

from __future__ import annotations

import os
from uuid import uuid4

import firebase_admin
import requests
from firebase_admin import auth
from seed_qi_integrated_experience import (
    PROJECT,
    TARGET_EMAIL,
    TARGET_PASSWORD,
    User,
    admin_session,
    call,
    firebase_api_key,
    token_for_email,
)

BASE_URL = os.environ["PAIRPILOT_BASE_URL"].rstrip("/")


def live_turn(user: User, conversation_id: str, task_id: str, content: str) -> str:
    response = requests.post(
        f"{BASE_URL}/api/v1/conversations/{conversation_id}/messages",
        headers={
            "Authorization": f"Bearer {user.token}",
            "Content-Type": "application/json",
        },
        json={
            "content": content,
            "client_message_id": f"qi-persistent-{uuid4().hex}",
            "task_id": task_id,
            "retry_of": None,
        },
        timeout=240,
    )
    response.raise_for_status()
    transcript = response.text
    if "event: agent.error" in transcript or "event: agent.completed" not in transcript:
        raise RuntimeError("The live Personal Agent turn did not complete cleanly.")
    return transcript


def main() -> None:
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": PROJECT})
    record = auth.get_user_by_email(TARGET_EMAIL)
    api_key = firebase_api_key(admin_session())
    user = User(
        uid=record.uid,
        token=token_for_email(TARGET_EMAIL, TARGET_PASSWORD, api_key),
        email=TARGET_EMAIL,
        display_name="Qi Zhang",
    )
    state = call(user, "GET", "/api/app/bootstrap")
    task = next(
        item
        for item in state["tasks"]
        if item.get("task_type") == "EVENT_BUDDY"
        and "迪士尼" in str(item.get("title", ""))
    )
    conversation_id = f"user:{user.uid}:global"
    first = live_turn(
        user,
        conversation_id,
        str(task["task_id"]),
        (
            "请只查看并简短告诉我这个迪士尼 request 目前有几个候选，"
            "不要创建新任务或修改任何数据。"
        ),
    )
    second = live_turn(
        user,
        conversation_id,
        str(task["task_id"]),
        (
            "继续刚才同一个对话，请只简短告诉我现在有几个 rooms 和 matches，"
            "不要修改任何数据。"
        ),
    )
    assert "event: agent.completed" in first
    assert "event: agent.completed" in second
    print("PASS: two consecutive task-focused turns completed in one global chat")


if __name__ == "__main__":
    main()
