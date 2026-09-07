"""Authorized Startup V2 marketplace search and saved-search operations."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pairpilot_schemas import ExploreSearchInput, SaveSearchInput

from pairpilot_orchestrator.auth.authorization import (
    require_resource_owner,
    require_task_owner,
)
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.multi_user_platform import (
    PRODUCTION_NAMESPACE,
    SCHEMA_VERSION,
    MultiUserStore,
    stable_id,
)
from pairpilot_orchestrator.v1_foundation import (
    DEFAULT_COMMUNITY_ID,
    active_community_ids,
    create_notification,
    normalize_intent_type,
)

DISCOVERABLE_STATUS = "OPEN"
TERMINAL_OR_HIDDEN_STATUSES = {
    "MATCHED",
    "CLOSED",
    "PAUSED",
    "EXPIRED",
    "CANCELLED",
}
TOKEN_PATTERN = re.compile(r"[\w'-]+", re.UNICODE)


def _clean(document: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if not key.startswith("_")}


def _normalized_intent_type(value: object) -> str | None:
    try:
        return normalize_intent_type(str(value or ""))
    except ValueError:
        return None


def is_explicit_demo_post(post: Mapping[str, Any]) -> bool:
    """Recognize only explicit synthetic labels; never guess from user behavior."""

    if post.get("demo_data") is True or post.get("test_data") is True:
        return True
    title = str(post.get("public_title") or "").casefold()
    display_name = str(post.get("public_display_name") or "").casefold()
    return (
        title.startswith("controlled demo:")
        or " — test multi-" in title
        or "· simulated tester" in display_name
        or "controlled demo" in display_name
        or "controlled test" in display_name
    )


def public_post_projection(post: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "schema_version",
        "intent_id",
        "owner_agent_id",
        "community_id",
        "public_display_name",
        "task_type",
        "public_title",
        "public_summary",
        "public_constraints",
        "public_requirements",
        "status",
        "capacity",
        "capacity_remaining",
        "authorship",
        "human_approval_status",
        "published_at",
        "expires_at",
        "updated_at",
    }
    return {key: value for key, value in post.items() if key in allowed}


def _tokens(value: object) -> set[str]:
    if isinstance(value, Mapping):
        return (
            set().union(*(_tokens(item) for item in value.values())) if value else set()
        )
    if isinstance(value, list):
        return set().union(*(_tokens(item) for item in value)) if value else set()
    return {
        match.group(0).casefold() for match in TOKEN_PATTERN.finditer(str(value or ""))
    }


def _as_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _as_datetime(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _structured_match(post: Mapping[str, Any], body: ExploreSearchInput) -> bool:
    constraints = post.get("public_constraints")
    public_constraints = constraints if isinstance(constraints, Mapping) else {}
    if body.community_id and post.get("community_id") != body.community_id:
        return False
    if body.intent_type and _normalized_intent_type(
        post.get("task_type")
    ) != _normalized_intent_type(body.intent_type):
        return False
    if (
        body.location
        and body.location.casefold()
        not in str(public_constraints.get("location", "")).casefold()
    ):
        return False
    if int(post.get("capacity_remaining", 0)) < body.minimum_capacity:
        return False
    post_start = _as_date(public_constraints.get("date_start"))
    post_end = _as_date(public_constraints.get("date_end"))
    if body.date_start and post_end and post_end < body.date_start:
        return False
    if body.date_end and post_start and post_start > body.date_end:
        return False
    required_tags = {item.casefold() for item in body.tags}
    post_tags = {str(item).casefold() for item in post.get("public_requirements", [])}
    if required_tags and not required_tags.issubset(post_tags):
        return False
    if body.freshness_days:
        updated_at = _as_datetime(post.get("updated_at") or post.get("published_at"))
        if updated_at and updated_at < datetime.now(UTC) - timedelta(
            days=body.freshness_days
        ):
            return False
    return True


def _relevance(
    post: Mapping[str, Any], body: ExploreSearchInput
) -> tuple[float, list[str]]:
    query_tokens = _tokens(body.query)
    post_tokens = _tokens(
        {
            "title": post.get("public_title"),
            "summary": post.get("public_summary"),
            "requirements": post.get("public_requirements"),
            "constraints": post.get("public_constraints"),
            "type": post.get("task_type"),
        }
    )
    overlap = query_tokens & post_tokens
    text_score = len(overlap) / max(len(query_tokens), 1) if query_tokens else 0.5
    freshness = _as_datetime(post.get("updated_at") or post.get("published_at"))
    freshness_score = 0.0
    if freshness:
        age_days = max((datetime.now(UTC) - freshness.astimezone(UTC)).days, 0)
        freshness_score = max(0.0, 1.0 - age_days / 365)
    reasons = []
    if overlap:
        reasons.append(f"Matches: {', '.join(sorted(overlap)[:4])}")
    if body.community_id:
        reasons.append("In the selected Community")
    if body.intent_type:
        reasons.append("Compatible request type")
    if not reasons:
        reasons.append("Current open Post in your discovery scope")
    return round(text_score * 0.8 + freshness_score * 0.2, 4), reasons


async def _blocked_uids(
    store: MultiUserStore, principal: AuthenticatedPrincipal
) -> set[str]:
    outgoing = await store.query_documents(
        "blocks", filters=[("blocker_uid", "EQUAL", principal.uid)]
    )
    incoming = await store.query_documents(
        "blocks", filters=[("blocked_uid", "EQUAL", principal.uid)]
    )
    return {str(item.get("blocked_uid")) for item in outgoing} | {
        str(item.get("blocker_uid")) for item in incoming
    }


async def search_marketplace(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    body: ExploreSearchInput,
) -> dict[str, Any]:
    """Search bounded public projections; private Intent data is never loaded."""

    member_communities = set(await active_community_ids(store, principal.uid))
    blocked = await _blocked_uids(store, principal)
    task: dict[str, Any] | None = None
    if body.task_id:
        task = await store.get("task_workspaces", body.task_id)
        if task is None:
            raise LookupError("task was not found")
        require_task_owner(principal, task)
        if _normalized_intent_type(task.get("task_type")) is None:
            raise ValueError("LEGACY_TASK_TYPE_REQUIRES_MIGRATION")

    if body.view == "MY_POSTS":
        candidates = await store.query_documents(
            "intent_posts", filters=[("owner_uid", "EQUAL", principal.uid)]
        )
    else:
        candidates = await store.query_documents(
            "intent_posts", filters=[("status", "EQUAL", DISCOVERABLE_STATUS)]
        )

    # Load the viewer's active saves for every view so feed cards can render an
    # authoritative saved state. Previously this happened only on the Saved
    # tab, which made the same Post look unsaved everywhere else.
    saved = await store.query_documents(
        "saved_posts", filters=[("owner_uid", "EQUAL", principal.uid)]
    )
    saved_ids = {
        str(item.get("intent_id"))
        for item in saved
        if item.get("status", "ACTIVE") == "ACTIVE"
    }

    connected_agents: set[str] = set()
    if body.view == "FROM_CONNECTIONS":
        relationships = await store.query_documents(
            "relationships", filters=[("owner_uid", "EQUAL", principal.uid)]
        )
        connected_agents = {str(item.get("peer_agent_id")) for item in relationships}

    results: list[dict[str, Any]] = []
    for post in candidates:
        is_owner = post.get("owner_uid") == principal.uid
        if post.get("namespace") != PRODUCTION_NAMESPACE:
            continue
        if (
            PRODUCTION_NAMESPACE == "production"
            and not is_owner
            and is_explicit_demo_post(post)
        ):
            continue
        if not is_owner and (
            post.get("status") != DISCOVERABLE_STATUS
            or post.get("owner_uid") in blocked
            or str(post.get("community_id", DEFAULT_COMMUNITY_ID))
            not in member_communities
        ):
            continue
        intent_id = str(post.get("intent_id", ""))
        if body.view == "SAVED" and intent_id not in saved_ids:
            continue
        if (
            body.view == "FROM_CONNECTIONS"
            and str(post.get("owner_agent_id")) not in connected_agents
        ):
            continue
        if body.view != "MY_POSTS" and is_owner:
            continue
        if task and _normalized_intent_type(
            post.get("task_type")
        ) != _normalized_intent_type(task.get("task_type")):
            continue
        if not _structured_match(post, body):
            continue
        score, reasons = _relevance(post, body)
        if body.query and score <= 0.2:
            continue
        results.append(
            {
                **public_post_projection(post),
                "saved": intent_id in saved_ids,
                "relevance_score": score,
                "surfaced_reasons": reasons,
                "related_task_id": body.task_id,
            }
        )
    results.sort(
        key=lambda item: (
            float(item.get("relevance_score", 0)),
            str(item.get("updated_at") or item.get("published_at") or ""),
        ),
        reverse=True,
    )
    return {
        "items": results[: body.limit],
        "count": min(len(results), body.limit),
        "view": body.view,
        "retrieval": {
            "structured_filters": True,
            "semantic_vector": False,
            "text_relevance": True,
            "note": (
                "Vector retrieval is gated on candidate index and embedding backfill."
            ),
        },
    }


async def get_post_detail(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    intent_id: str,
) -> dict[str, Any]:
    post = await store.get("intent_posts", intent_id)
    if post is None or post.get("namespace") != PRODUCTION_NAMESPACE:
        raise LookupError("post was not found")
    is_owner = post.get("owner_uid") == principal.uid
    if not is_owner:
        if PRODUCTION_NAMESPACE == "production" and is_explicit_demo_post(post):
            raise LookupError("post was not found")
        if post.get("status") != DISCOVERABLE_STATUS:
            raise LookupError("post was not found")
        if str(post.get("community_id", DEFAULT_COMMUNITY_ID)) not in set(
            await active_community_ids(store, principal.uid)
        ):
            raise PermissionError("community membership is required")
        if post.get("owner_uid") in await _blocked_uids(store, principal):
            raise LookupError("post was not found")
    saved_id = stable_id("saved_post", principal.uid, intent_id)
    saved = await store.get("saved_posts", saved_id)
    return {
        "post": {**public_post_projection(post), "owned_by_viewer": is_owner},
        "saved": saved is not None and saved.get("status", "ACTIVE") == "ACTIVE",
    }


async def save_post(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    intent_id: str,
    task_id: str | None,
) -> dict[str, Any]:
    await get_post_detail(store, principal, intent_id)
    if task_id:
        task = await store.get("task_workspaces", task_id)
        if task is None:
            raise LookupError("task was not found")
        require_task_owner(principal, task)
    saved_id = stable_id("saved_post", principal.uid, intent_id)
    saved = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "saved_post_id": saved_id,
        "owner_uid": principal.uid,
        "intent_id": intent_id,
        "task_id": task_id,
        "status": "ACTIVE",
        "created_at": datetime.now(UTC),
    }
    # Re-saving after removal must reactivate the deterministic record instead
    # of silently returning its previous REMOVED state.
    existing = await store.get("saved_posts", saved_id)
    if existing is None:
        await store.create("saved_posts", saved_id, saved)
    else:
        await store.upsert("saved_posts", saved_id, saved)
    return _clean((await store.get("saved_posts", saved_id)) or saved)


async def unsave_post(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    *,
    intent_id: str,
) -> dict[str, Any]:
    saved_id = stable_id("saved_post", principal.uid, intent_id)
    saved = await store.get("saved_posts", saved_id)
    if saved is None:
        return {"saved_post_id": saved_id, "status": "NOT_SAVED"}
    require_resource_owner(principal, saved)
    clean = _clean(saved)
    clean.update(status="REMOVED", removed_at=datetime.now(UTC))
    await store.upsert("saved_posts", saved_id, clean)
    return {"saved_post_id": saved_id, "status": "REMOVED"}


async def create_saved_search(
    store: MultiUserStore,
    principal: AuthenticatedPrincipal,
    body: SaveSearchInput,
) -> dict[str, Any]:
    if body.search.task_id:
        task = await store.get("task_workspaces", body.search.task_id)
        if task is None:
            raise LookupError("task was not found")
        require_task_owner(principal, task)
    saved_search_id = stable_id(
        "saved_search",
        principal.uid,
        body.name.casefold(),
        body.search.model_dump_json(),
    )
    timestamp = datetime.now(UTC)
    document = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "saved_search_id": saved_search_id,
        "owner_uid": principal.uid,
        "name": body.name,
        "search": body.search.model_dump(mode="json"),
        "task_id": body.search.task_id,
        "monitor_enabled": body.monitor_enabled,
        "monitor_status": "ACTIVE" if body.monitor_enabled else "PAUSED",
        "notification_sensitivity": body.notification_sensitivity,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    await store.create("saved_searches", saved_search_id, document)
    await store.write_event(
        event_type="marketplace.saved_search.created.v2",
        run_id=saved_search_id,
        producer=str(principal.uid),
        payload={
            "savedSearchId": saved_search_id,
            "taskId": body.search.task_id,
            "monitorEnabled": body.monitor_enabled,
        },
        idempotency_key=f"v2:saved-search:{saved_search_id}:created",
    )
    return _clean((await store.get("saved_searches", saved_search_id)) or document)


async def _record_saved_search_hit(
    store: MultiUserStore,
    *,
    saved_search: Mapping[str, Any],
    post: Mapping[str, Any],
    now: datetime,
) -> bool:
    owner_uid = str(saved_search.get("owner_uid") or "")
    intent_id = str(post.get("intent_id") or "")
    saved_search_id = str(saved_search.get("saved_search_id") or "")
    if not owner_uid or not intent_id or not saved_search_id:
        return False
    if post.get("owner_uid") == owner_uid or post.get("status") != "OPEN":
        return False
    if post.get("namespace") != PRODUCTION_NAMESPACE:
        return False
    if PRODUCTION_NAMESPACE == "production" and is_explicit_demo_post(post):
        return False
    search = ExploreSearchInput.model_validate(saved_search.get("search") or {})
    communities = set(await active_community_ids(store, owner_uid))
    if str(post.get("community_id", DEFAULT_COMMUNITY_ID)) not in communities:
        return False
    viewer = AuthenticatedPrincipal(
        uid=owner_uid,
        email=None,
        email_verified=True,
    )
    if post.get("owner_uid") in await _blocked_uids(store, viewer):
        return False
    if search.task_id:
        task = await store.get("task_workspaces", search.task_id)
        if (
            task is None
            or task.get("owner_uid") != owner_uid
            or task.get("status") in {"COMPLETED", "CANCELLED"}
            or _normalized_intent_type(task.get("task_type"))
            != _normalized_intent_type(post.get("task_type"))
        ):
            return False
    if not _structured_match(post, search):
        return False
    score, reasons = _relevance(post, search)
    minimum_score = {
        "HIGH": 0.2,
        "MEANINGFUL": 0.35,
        "LOW": 0.55,
    }.get(str(saved_search.get("notification_sensitivity")), 0.35)
    if search.query and score <= minimum_score:
        return False
    hit_id = stable_id("saved_search_hit", saved_search_id, intent_id)
    hit = {
        "schema_version": SCHEMA_VERSION,
        "namespace": PRODUCTION_NAMESPACE,
        "saved_search_hit_id": hit_id,
        "saved_search_id": saved_search_id,
        "owner_uid": owner_uid,
        "intent_id": intent_id,
        "task_id": saved_search.get("task_id"),
        "relevance_score": score,
        "surfaced_reasons": reasons,
        "status": "NOTIFIED",
        "created_at": now,
    }
    if not await store.create("saved_search_hits", hit_id, hit):
        return False
    entity_ids = [intent_id]
    if saved_search.get("task_id"):
        entity_ids.append(str(saved_search["task_id"]))
    await create_notification(
        store,
        owner_uid=owner_uid,
        notification_type="SAVED_SEARCH_MATCH",
        title=f"New Post matches {str(saved_search.get('name') or 'your monitor')}",
        body=str(post.get("public_title") or "A new public Post is available."),
        entity_ids=entity_ids,
        idempotency_key=f"saved-search:{saved_search_id}:{intent_id}",
        now=now,
    )
    return True


async def evaluate_saved_searches_for_post(
    store: MultiUserStore,
    intent_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Evaluate one newly published public Post against active monitors."""

    post = await store.get("intent_posts", intent_id)
    if post is None:
        return {"searches_evaluated": 0, "new_matches": 0}
    searches = await store.query_documents(
        "saved_searches", filters=[("monitor_status", "EQUAL", "ACTIVE")], limit=100
    )
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    matched = 0
    for saved_search in searches:
        if await _record_saved_search_hit(
            store,
            saved_search=saved_search,
            post=post,
            now=timestamp,
        ):
            matched += 1
    return {"searches_evaluated": len(searches), "new_matches": matched}


async def evaluate_saved_search(
    store: MultiUserStore,
    saved_search_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Evaluate a newly enabled monitor against currently open Posts."""

    saved_search = await store.get("saved_searches", saved_search_id)
    if saved_search is None or saved_search.get("monitor_status") != "ACTIVE":
        return {"posts_evaluated": 0, "new_matches": 0}
    posts = await store.query_documents(
        "intent_posts", filters=[("status", "EQUAL", "OPEN")], limit=100
    )
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    matched = 0
    for post in posts:
        if await _record_saved_search_hit(
            store,
            saved_search=saved_search,
            post=post,
            now=timestamp,
        ):
            matched += 1
    return {"posts_evaluated": len(posts), "new_matches": matched}
