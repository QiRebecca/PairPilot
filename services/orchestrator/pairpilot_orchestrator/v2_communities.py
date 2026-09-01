"""Privacy-safe operational Communities for Startup V2."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal
from pairpilot_orchestrator.multi_user_platform import PRODUCTION_NAMESPACE
from pairpilot_orchestrator.v2_marketplace import (
    is_explicit_demo_post,
    public_post_projection,
)

DEFAULT_RULES = [
    "Only publish information you are comfortable sharing with Community members.",
    (
        "Keep precise live location, room numbers, contact details, and protected "
        "Memory private."
    ),
    (
        "Personal Agents must ask before identity disclosure, booking, payment, "
        "or commitment."
    ),
    "Adults only. Report unsafe, misleading, or abusive behavior to moderators.",
]
PUBLIC_COMMUNITY_TYPES = {"PUBLIC"}
MEMBER_ROLES = {"MEMBER", "MODERATOR", "ADMIN", "COMMUNITY_AGENT"}
COMMUNITY_ROOM_VISIBILITIES = {"COMMUNITY", "COMMUNITY_MEMBERS"}
TOKEN_PATTERN = re.compile(r"[\w'-]+", re.UNICODE)


def _clean(document: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if not key.startswith("_")}


def _is_explicit_demo_identity(user: Mapping[str, Any]) -> bool:
    if user.get("demo_data") is True or user.get("test_data") is True:
        return True
    display_name = str(user.get("display_name") or "").casefold()
    return any(
        marker in display_name
        for marker in (
            "controlled demo",
            "controlled test",
            "simulated tester",
            "test account",
        )
    )


def membership_type(community: Mapping[str, Any]) -> str:
    explicit = str(community.get("membership_type") or "").upper()
    if explicit in {
        "PUBLIC",
        "INVITE_LINK",
        "APPROVAL_REQUIRED",
        "DOMAIN_VERIFIED",
        "PRIVATE",
    }:
        return explicit
    policy = str(community.get("membership_policy") or "").upper()
    visibility = str(community.get("visibility") or "").upper()
    if policy == "PUBLIC_JOIN" and visibility == "PUBLIC":
        return "PUBLIC"
    if policy == "INVITE_REQUIRED":
        return "INVITE_LINK"
    return "PRIVATE"


def _public_community(community: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "schema_version",
        "community_id",
        "name",
        "description",
        "purpose",
        "type",
        "location",
        "start_time",
        "end_time",
        "status",
    }
    projected = {key: value for key, value in community.items() if key in allowed}
    projected["membership_type"] = membership_type(community)
    rules = community.get("rules")
    projected["rules"] = (
        [str(rule) for rule in rules if str(rule).strip()]
        if isinstance(rules, list)
        else DEFAULT_RULES
    )
    return projected


async def _membership(
    store: Any, owner_uid: str, community_id: str
) -> dict[str, Any] | None:
    records = await store.query_documents(
        "community_memberships", filters=[("owner_uid", "EQUAL", owner_uid)]
    )
    return next(
        (
            _clean(item)
            for item in records
            if item.get("community_id") == community_id
            and item.get("status") == "ACTIVE"
        ),
        None,
    )


async def _require_visible_community(
    store: Any, principal: AuthenticatedPrincipal, community_id: str
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    community = await store.get("communities", community_id)
    if (
        community is None
        or community.get("status") != "ACTIVE"
        or community.get("namespace", PRODUCTION_NAMESPACE) != PRODUCTION_NAMESPACE
    ):
        raise LookupError("community was not found")
    viewer_membership = await _membership(store, principal.uid, community_id)
    if (
        membership_type(community) not in PUBLIC_COMMUNITY_TYPES
        and not viewer_membership
    ):
        raise LookupError("community was not found")
    return community, viewer_membership


async def _public_members(
    store: Any,
    community_id: str,
    viewer_uid: str,
    relationships: list[Mapping[str, Any]],
    memberships: list[Mapping[str, Any]],
    community_posts: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    users, privacy_configs, agents = await asyncio.gather(
        store.query_documents("users", filters=[], limit=100),
        store.query_documents("user_privacy_configs", filters=[], limit=100),
        store.query_documents("personal_agents", filters=[], limit=100),
    )
    users_by_uid = {
        str(item.get("uid") or item.get("owner_uid")): item for item in users
    }
    privacy_by_uid = {str(item.get("owner_uid")): item for item in privacy_configs}
    agents_by_id = {str(item.get("agent_id")): item for item in agents}
    connected_agents = {
        str(item.get("peer_agent_id"))
        for item in relationships
        if item.get("status", "ACTIVE") == "ACTIVE"
    }
    result: list[dict[str, Any]] = []
    for membership in memberships:
        if membership.get("status") != "ACTIVE":
            continue
        uid = str(membership.get("owner_uid") or "")
        role = str(membership.get("role") or "MEMBER").upper()
        if not uid or role not in MEMBER_ROLES:
            continue
        user = users_by_uid.get(uid)
        if (
            user is None
            or user.get("account_status", "ACTIVE") != "ACTIVE"
            or (
                PRODUCTION_NAMESPACE == "production"
                and uid != viewer_uid
                and _is_explicit_demo_identity(user)
            )
        ):
            continue
        privacy = privacy_by_uid.get(uid)
        is_viewer = uid == viewer_uid
        if (
            not is_viewer
            and privacy
            and privacy.get("public_profile_visible") is not True
        ):
            continue
        agent_id = str(user.get("personal_agent_id") or "")
        agent = agents_by_id.get(agent_id)
        interests = user.get("public_interests")
        result.append(
            {
                "display_name": str(user.get("display_name") or "Community member"),
                "personal_agent": str(
                    (agent or {}).get("display_name") or "Personal Agent"
                ),
                "personal_agent_id": agent_id,
                "role": role,
                "public_interests": (
                    [str(item) for item in interests[:8]]
                    if isinstance(interests, list)
                    else []
                ),
                "open_post_count": sum(
                    1
                    for post in community_posts
                    if post.get("community_id") == community_id
                    and post.get("owner_uid") == uid
                    and post.get("status") == "OPEN"
                    and (
                        PRODUCTION_NAMESPACE != "production"
                        or not is_explicit_demo_post(post)
                    )
                ),
                "shared_connection": agent_id in connected_agents,
                "is_viewer": is_viewer,
            }
        )
    result.sort(key=lambda item: (not item["is_viewer"], item["display_name"]))
    return result


async def get_community_detail(
    store: Any, principal: AuthenticatedPrincipal, community_id: str
) -> dict[str, Any]:
    community, viewer_membership = await _require_visible_community(
        store, principal, community_id
    )
    memberships, posts, relationships = await asyncio.gather(
        store.query_documents(
            "community_memberships", filters=[("community_id", "EQUAL", community_id)]
        ),
        store.query_documents(
            "intent_posts", filters=[("community_id", "EQUAL", community_id)]
        ),
        store.query_documents(
            "relationships", filters=[("owner_uid", "EQUAL", principal.uid)]
        ),
    )
    open_posts = [
        public_post_projection(post)
        for post in posts
        if post.get("namespace", PRODUCTION_NAMESPACE) == PRODUCTION_NAMESPACE
        and post.get("status") == "OPEN"
        and (PRODUCTION_NAMESPACE != "production" or not is_explicit_demo_post(post))
    ]
    members: list[dict[str, Any]] = []
    rooms: list[dict[str, Any]] = []
    if viewer_membership:
        members, candidate_rooms = await asyncio.gather(
            _public_members(
                store,
                community_id,
                principal.uid,
                relationships,
                memberships,
                posts,
            ),
            store.query_documents(
                "coordination_rooms",
                filters=[("community_id", "EQUAL", community_id)],
            ),
        )
        for room in candidate_rooms:
            participants = room.get("participant_uids")
            is_participant = (
                isinstance(participants, list) and principal.uid in participants
            )
            if (
                not is_participant
                and str(room.get("visibility") or "").upper()
                not in COMMUNITY_ROOM_VISIBILITIES
            ):
                continue
            rooms.append(
                {
                    key: value
                    for key, value in room.items()
                    if key
                    in {
                        "room_id",
                        "title",
                        "room_type",
                        "state",
                        "status",
                        "visibility",
                        "participant_display_names",
                        "last_material_update",
                        "updated_at",
                    }
                }
            )
    grouped = {
        intent_type: [
            post for post in open_posts if post.get("task_type") == intent_type
        ]
        for intent_type in (
            "ROOM_SHARE",
            "MEAL_COMPANION",
            "COFFEE_CHAT",
            "EVENT_BUDDY",
            "HACKATHON_TEAMMATE",
        )
    }
    active_memberships = [
        item for item in memberships if item.get("status") == "ACTIVE"
    ]
    moderator_names = [
        item["display_name"]
        for item in members
        if item["role"] in {"MODERATOR", "ADMIN"}
    ]
    return {
        "community": _public_community(community),
        "viewer": {
            "joined": viewer_membership is not None,
            "role": (viewer_membership or {}).get("role"),
            "can_moderate": str((viewer_membership or {}).get("role") or "").upper()
            in {"MODERATOR", "ADMIN"},
        },
        "counts": {
            "members": len(members) if viewer_membership else len(active_memberships),
            "active_posts": len(open_posts),
            "active_plans": len(rooms),
        },
        "moderators": moderator_names,
        "open_requests": grouped if viewer_membership else {},
        "members": members,
        "plans_and_rooms": rooms,
        "privacy": {
            "public_overview": True,
            "member_directory_requires_membership": True,
            "login_email_exposed": False,
            "private_messages_exposed": False,
        },
    }


def _question_tokens(value: str) -> set[str]:
    return {match.group(0).casefold() for match in TOKEN_PATTERN.finditer(value)}


async def query_community_agent(
    store: Any,
    principal: AuthenticatedPrincipal,
    community_id: str,
    question: str,
) -> dict[str, Any]:
    """Answer only from the same public/member-safe projection used by the UI."""

    detail = await get_community_detail(store, principal, community_id)
    community = detail["community"]
    tokens = _question_tokens(question)
    posts = [post for group in detail["open_requests"].values() for post in group]
    if tokens & {"rule", "rules", "safe", "safety", "privacy"}:
        answer = "Community rules: " + " ".join(community["rules"])
        surfaced: list[dict[str, Any]] = []
    elif tokens & {"post", "posts", "request", "requests", "find", "looking"}:
        ranked = []
        for post in posts:
            haystack = _question_tokens(
                " ".join(
                    [
                        str(post.get("public_title") or ""),
                        str(post.get("public_summary") or ""),
                        " ".join(map(str, post.get("public_requirements") or [])),
                    ]
                )
            )
            ranked.append((len(tokens & haystack), post))
        ranked.sort(key=lambda item: item[0], reverse=True)
        surfaced = [item[1] for item in ranked[:3] if item[0] > 0]
        if not surfaced:
            surfaced = [item[1] for item in ranked[:3]]
        answer = (
            f"I found {len(posts)} open Community request(s). "
            f"Here are {len(surfaced)} public result(s) related to your question."
        )
    else:
        purpose = community.get("purpose") or community.get("description")
        answer = (
            f"{community.get('name')} is for {purpose}. "
            f"It currently has {detail['counts']['members']} member(s) and "
            f"{detail['counts']['active_posts']} open request(s)."
        )
        surfaced = []
    return {
        "agent": {
            "agent_id": f"community_agent:{community_id}",
            "display_name": f"{community.get('name')} Community Agent",
            "role": "COMMUNITY_AGENT",
        },
        "answer": answer,
        "surfaced_posts": surfaced,
        "scope": "COMMUNITY_PUBLIC_AND_MEMBER_SAFE",
        "provenance": [
            "community record",
            "community rules",
            "public Post projections",
        ],
        "restrictions": [
            "No protected Memory",
            "No private task transcript",
            "No Agent-only negotiation",
            "No private membership data",
        ],
        "answered_at": datetime.now(UTC),
    }
