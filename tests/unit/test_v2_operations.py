from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.multi_user_platform import provision_user
from pairpilot_orchestrator.v2_operations import (
    build_operations_console,
    get_admin_report,
    list_community_reports,
    moderate_report,
    operate_failed_job,
    update_user_quota,
)
from test_multi_user_platform import MemoryMultiUserStore


def principal(uid: str, *, admin: bool = False) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        uid=uid,
        email=f"{uid}@private.example",
        email_verified=True,
        admin=admin,
    )


@pytest.mark.asyncio
async def test_operations_console_requires_admin_and_excludes_private_content() -> None:
    store = MemoryMultiUserStore()
    await store.create(
        "users",
        "member",
        {
            "uid": "member",
            "display_name": "Member",
            "email": "never-expose@example.com",
            "account_status": "ACTIVE",
        },
    )
    await store.create(
        "reports",
        "report_one",
        {
            "report_id": "report_one",
            "target_type": "POST",
            "target_id": "post_one",
            "category": "SAFETY",
            "details": "sensitive report narrative",
            "status": "OPEN",
        },
    )
    await store.create(
        "memories",
        "memory_one",
        {"memory_id": "memory_one", "status": "PROPOSED", "content": "secret"},
    )
    with pytest.raises(HTTPException) as denied:
        await build_operations_console(store, principal("member"))
    assert denied.value.status_code == 403

    dashboard = await build_operations_console(store, principal("operator", admin=True))
    serialized = json.dumps(dashboard, default=str)
    assert dashboard["access"] == "SERVER_VERIFIED_ADMIN_CLAIM"
    assert dashboard["reports"][0]["details_available"] is True
    assert "never-expose@example.com" not in serialized
    assert "sensitive report narrative" not in serialized
    assert '"content": "secret"' not in serialized


@pytest.mark.asyncio
async def test_report_detail_is_explicit_and_moderation_is_audited() -> None:
    store = MemoryMultiUserStore()
    admin = principal("operator", admin=True)
    await store.create(
        "intent_posts",
        "post_one",
        {
            "intent_id": "post_one",
            "owner_uid": "reported",
            "community_id": "community_one",
            "status": "OPEN",
        },
    )
    await store.create(
        "reports",
        "report_one",
        {
            "report_id": "report_one",
            "reporter_uid": "reporter",
            "target_type": "POST",
            "target_id": "post_one",
            "community_id": "community_one",
            "category": "SPAM",
            "details": "The public Post repeats unwanted advertising.",
            "status": "OPEN",
        },
    )
    detail = await get_admin_report(store, admin, "report_one")
    assert detail["details"].startswith("The public Post")
    result = await moderate_report(
        store,
        admin,
        report_id="report_one",
        action="REMOVE_POST",
        reason="Confirmed repeated advertising",
    )
    assert result["status"] == "RESOLVED"
    assert (await store.get("intent_posts", "post_one"))["status"] == "CLOSED"
    assert len(store.collections["moderation_actions"]) == 1
    assert len(store.collections["audit_events"]) == 1


@pytest.mark.asyncio
async def test_community_moderator_scope_is_enforced() -> None:
    store = MemoryMultiUserStore()
    moderator = principal("moderator")
    member = principal("member")
    await store.create(
        "community_memberships",
        "membership_moderator",
        {
            "membership_id": "membership_moderator",
            "community_id": "community_one",
            "owner_uid": moderator.uid,
            "role": "MODERATOR",
            "status": "ACTIVE",
        },
    )
    await store.create(
        "reports",
        "report_one",
        {
            "report_id": "report_one",
            "community_id": "community_one",
            "target_type": "USER",
            "target_id": "reported",
            "category": "HARASSMENT",
            "details": "Community-scoped report.",
            "status": "OPEN",
        },
    )
    queue = await list_community_reports(store, moderator, "community_one")
    assert [item["report_id"] for item in queue["reports"]] == ["report_one"]
    with pytest.raises(HTTPException) as denied:
        await list_community_reports(store, member, "community_one")
    assert denied.value.status_code == 403
    with pytest.raises(HTTPException) as wrong_community:
        await list_community_reports(store, moderator, "community_two")
    assert wrong_community.value.status_code == 403


@pytest.mark.asyncio
async def test_failed_job_retry_is_idempotent_and_content_free() -> None:
    store = MemoryMultiUserStore()
    admin = principal("operator", admin=True)
    await store.create(
        "job_failures",
        "job_one",
        {
            "job_id": "job_one",
            "task_id": "task_one",
            "job_type": "CANDIDATE_EVALUATION",
            "status": "FAILED",
            "error_type": "TRANSIENT_PROVIDER_ERROR",
            "private_payload": "must not enter retry event",
            "attempt_count": 1,
            "created_at": datetime.now(UTC),
        },
    )
    first = await operate_failed_job(
        store,
        admin,
        job_id="job_one",
        action="RETRY",
        idempotency_key="retry-key-one",
        reason="Transient provider recovery",
    )
    second = await operate_failed_job(
        store,
        admin,
        job_id="job_one",
        action="RETRY",
        idempotency_key="retry-key-one",
        reason="Transient provider recovery",
    )
    assert first["operation_id"] == second["operation_id"]
    assert (await store.get("job_failures", "job_one"))["attempt_count"] == 2
    assert len(store.collections["events"]) == 1
    assert "private_payload" not in json.dumps(store.collections["events"], default=str)


@pytest.mark.asyncio
async def test_quota_update_requires_admin_and_is_audited() -> None:
    store = MemoryMultiUserStore()
    owner = principal("owner")
    await provision_user(store, owner)
    values = {
        "active_task_limit": 8,
        "concurrent_negotiations_per_task": 3,
        "new_contacts_per_task": 12,
        "daily_agent_turn_limit": 80,
    }
    with pytest.raises(HTTPException):
        await update_user_quota(
            store,
            owner,
            owner_uid=owner.uid,
            values=values,
            reason="Unauthorized increase",
        )
    updated = await update_user_quota(
        store,
        principal("operator", admin=True),
        owner_uid=owner.uid,
        values=values,
        reason="Approved closed-beta cohort allocation",
    )
    assert updated["daily_agent_turn_limit"] == 80
    assert len(store.collections["audit_events"]) == 1
