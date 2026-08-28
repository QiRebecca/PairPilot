"""Public demo API and static frontend for the PairPilot golden path."""

from __future__ import annotations

import asyncio
import json
import os
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from pairpilot_orchestrator.config import LIVE_MODE, Settings
from pairpilot_orchestrator.domain import (
    AuthorityError,
    commit_approved_match,
    create_human_approval,
)
from pairpilot_orchestrator.infrastructure import GoogleCloudStore
from pairpilot_orchestrator.run_golden_path import GOAL_TEXT, run

MAX_PUBLIC_RUNS_PER_UTC_DAY = 12
MAX_REQUESTS_PER_MINUTE = 120
POLL_SECONDS = 1.5
PUBLIC_COLLECTIONS = (
    "runs",
    "agent_turns",
    "agent_messages",
    "beliefs",
    "proposals",
    "holds",
    "approval_requests",
    "approvals",
    "matches",
    "relationships",
    "relationship_events",
    "memories",
)

app = FastAPI(
    title="PairPilot — The Relationship Layer for Personal Agents",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)
_run_lock = asyncio.Lock()
_requests: defaultdict[str, deque[float]] = defaultdict(deque)


class ApprovalBody(BaseModel):
    """An explicit authorization for one visible proposal version."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    proposal_id: str
    proposal_version: int
    confirmation: str


class RejectBody(BaseModel):
    """A rejection for one visible proposal version."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    proposal_id: str
    proposal_version: int


def _store() -> GoogleCloudStore:
    settings = Settings.from_environment()
    return GoogleCloudStore(project_id=settings.project_id)


def _clean(item: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if not key.startswith("_")}


def _for_run(items: list[dict[str, Any]], run_id: str) -> list[dict[str, Any]]:
    return [_clean(item) for item in items if item.get("runId") == run_id]


def _sort_time(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: str(
            item.get("createdAt")
            or item.get("receivedAt")
            or item.get("requestedAt")
            or item.get("startedAt")
            or ""
        ),
    )


async def public_state(run_id: str | None = None) -> dict[str, Any]:
    """Return observable demo state without any private profile contents."""

    store = _store()
    loaded = await asyncio.gather(
        *(store.list_documents(collection) for collection in PUBLIC_COLLECTIONS)
    )
    data = dict(zip(PUBLIC_COLLECTIONS, loaded, strict=True))
    runs = sorted(data["runs"], key=lambda item: str(item.get("startedAt", "")))
    selected = (
        next((item for item in runs if item.get("runId") == run_id), None)
        if run_id
        else (runs[-1] if runs else None)
    )
    selected_id = str(selected.get("runId")) if selected else ""
    turns = _sort_time(_for_run(data["agent_turns"], selected_id))
    messages = _sort_time(
        [
            {
                "messageId": item.get("message_id"),
                "fromAgentId": item.get("from_agent_id"),
                "toAgentId": item.get("to_agent_id"),
                "speechAct": item.get("speech_act"),
                "naturalLanguage": item.get("natural_language"),
                "route": item.get("route"),
                "receivedAt": item.get("receivedAt"),
                "claimsAreAuthoritativeFacts": False,
            }
            for item in data["agent_messages"]
            if item.get("run_id") == selected_id
        ]
    )
    beliefs = [
        {
            "subjectAgentId": item.get("subject_agent_id")
            or item.get("subjectAgentId"),
            "field": item.get("field"),
            "value": item.get("value"),
            "kind": item.get("kind"),
            "observableReason": item.get("observableReason"),
            "authoritativeFact": False,
        }
        for item in data["beliefs"]
        if item.get("runId") == selected_id
    ]
    proposals = _for_run(data["proposals"], selected_id)
    holds = _for_run(data["holds"], selected_id)
    approval_requests = _for_run(data["approval_requests"], selected_id)
    approvals = _for_run(data["approvals"], selected_id)
    matches = _for_run(data["matches"], selected_id)
    now = datetime.now(UTC)
    for hold in holds:
        expires = datetime.fromisoformat(str(hold["expires_at"]).replace("Z", "+00:00"))
        hold["expired"] = expires <= now
    return {
        "product": "PairPilot",
        "executionMode": LIVE_MODE,
        "exactModelId": "gemini-3.7-flash",
        "goal": GOAL_TEXT,
        "run": _clean(selected) if selected else None,
        "turns": turns,
        "messages": messages,
        "beliefs": beliefs,
        "proposals": proposals,
        "holds": holds,
        "approvalRequests": approval_requests,
        "approvals": approvals,
        "matches": matches,
        "relationships": [_clean(item) for item in data["relationships"]],
        "relationshipEvents": [
            _clean(item) for item in data["relationship_events"]
        ],
        "memories": _for_run(data["memories"], selected_id),
        "protectedMemoryCount": 1,
        "limits": {
            "maximumGlobalTurns": 12,
            "maximumMessagesPerPair": 4,
            "maximumActiveCandidates": 2,
            "maximumWallClockSeconds": 90,
            "publicRunsPerUtcDay": MAX_PUBLIC_RUNS_PER_UTC_DAY,
        },
    }


async def _check_run_quota() -> None:
    today = datetime.now(UTC).date().isoformat()
    runs = await _store().list_documents("runs")
    today_count = sum(str(item.get("startedAt", "")).startswith(today) for item in runs)
    if today_count >= MAX_PUBLIC_RUNS_PER_UTC_DAY:
        raise HTTPException(429, "The safe public demo quota is exhausted for today.")


def _sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


async def _run_stream(run_id: UUID) -> AsyncIterator[str]:
    task = asyncio.create_task(run(run_id=run_id))
    previous = ""
    try:
        yield _sse("started", {"runId": str(run_id)})
        while not task.done():
            snapshot = await public_state(str(run_id))
            encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
            if encoded != previous:
                previous = encoded
                yield _sse("snapshot", snapshot)
            await asyncio.sleep(POLL_SECONDS)
        result = await task
        yield _sse("snapshot", await public_state(str(run_id)))
        yield _sse("complete", result)
    except asyncio.CancelledError:
        await asyncio.shield(task)
        raise
    finally:
        _run_lock.release()


@app.middleware("http")
async def rate_limit(request: Request, call_next: Any) -> Any:
    """Apply a small per-instance abuse bound to public API traffic."""

    if request.url.path.startswith("/api/"):
        forwarded = request.headers.get("x-forwarded-for", "")
        client = forwarded.split(",", 1)[0].strip() or (
            request.client.host if request.client else "unknown"
        )
        now = monotonic()
        bucket = _requests[client]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= MAX_REQUESTS_PER_MINUTE:
            return JSONResponse(
                {"detail": "Request rate limit exceeded."}, status_code=429
            )
        bucket.append(now)
    return await call_next(request)


@app.get("/api/health")
async def health() -> dict[str, str]:
    settings = Settings.from_environment()
    return {
        "status": "ok",
        "service": "pairpilot-orchestrator",
        "executionMode": settings.execution_mode,
        "exactModelId": settings.model_id,
    }


@app.get("/api/demo/state")
async def state(run_id: str | None = None) -> dict[str, Any]:
    return await public_state(run_id)


@app.get("/api/demo/run/stream")
async def start_run() -> StreamingResponse:
    if _run_lock.locked():
        raise HTTPException(409, "A live public demo run is already active.")
    await _check_run_quota()
    await _run_lock.acquire()
    run_id = uuid4()
    return StreamingResponse(
        _run_stream(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/demo/reset")
async def reset_demo() -> dict[str, Any]:
    if _run_lock.locked():
        raise HTTPException(409, "Cannot reset while a run is active.")
    from infra.seed_demo import reset_workflow, seed

    project_id = Settings.from_environment().project_id
    deleted = await asyncio.to_thread(reset_workflow, project_id)
    seeded = await asyncio.to_thread(seed, project_id, dry_run=False)
    return {"status": "RESET", "deleted": deleted, "seeded": seeded}


@app.post("/api/demo/approve")
async def approve(body: ApprovalBody) -> dict[str, Any]:
    required = f"APPROVE VERSION {body.proposal_version}"
    if body.confirmation != required:
        raise HTTPException(400, "Exact current-version approval is required.")
    store = _store()
    request_id = f"{body.proposal_id}-v{body.proposal_version}"
    approval_request = await store.get("approval_requests", request_id)
    if approval_request is None or approval_request.get("runId") != body.run_id:
        raise HTTPException(404, "Current approval request was not found.")
    try:
        approval = await create_human_approval(
            store=store,
            run_id=body.run_id,
            proposal_id=body.proposal_id,
            proposal_version=body.proposal_version,
            disclosure_hash=str(approval_request["disclosureHash"]),
        )
        match = await commit_approved_match(
            store=store,
            run_id=body.run_id,
            proposal_id=body.proposal_id,
        )
    except AuthorityError as exc:
        raise HTTPException(409, f"Commit blocked safely: {exc}") from exc
    return {"status": "COMMITTED", "approval": approval, "match": match}


@app.post("/api/demo/reject")
async def reject(body: RejectBody) -> dict[str, str]:
    store = _store()
    request_id = f"{body.proposal_id}-v{body.proposal_version}"
    approval_request = await store.get("approval_requests", request_id)
    if approval_request is None or approval_request.get("runId") != body.run_id:
        raise HTTPException(404, "Current approval request was not found.")
    hold = await store.get("holds", str(approval_request["holdId"]))
    if hold:
        hold["active"] = False
        hold.pop("_updateTime", None)
        await store.upsert("holds", str(approval_request["holdId"]), hold)
    approval_request["status"] = "REJECTED"
    approval_request["rejectedAt"] = datetime.now(UTC)
    approval_request.pop("_updateTime", None)
    await store.upsert("approval_requests", request_id, approval_request)
    await store.upsert(
        "runs",
        body.run_id,
        {
            "runId": body.run_id,
            "status": "USER_REJECTED",
            "updatedAt": datetime.now(UTC),
            "exactModelId": "gemini-3.7-flash",
            "executionMode": LIVE_MODE,
        },
    )
    return {"status": "USER_REJECTED"}


WEB_DIST = Path(os.environ.get("PAIRPILOT_WEB_DIST", "web/dist")).resolve()
if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/og.png", include_in_schema=False)
    async def social_card() -> FileResponse:
        return FileResponse(WEB_DIST / "og.png", media_type="image/png")

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(request: Request, path: str) -> HTMLResponse:
        origin = os.environ.get("PAIRPILOT_PUBLIC_BASE_URL", "").rstrip("/")
        if not origin:
            origin = str(request.base_url).rstrip("/")
        html = (WEB_DIST / "index.html").read_text().replace(
            "__PAIRPILOT_ORIGIN__", origin
        )
        return HTMLResponse(html)
