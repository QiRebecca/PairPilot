"""Central resource authorization helpers for the multi-user API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NoReturn

from fastapi import HTTPException

from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal


def _forbidden(code: str = "FORBIDDEN") -> NoReturn:
    raise HTTPException(
        status_code=403,
        detail={"code": code, "message": "You cannot access this resource."},
    )


def require_verified_email(
    principal: AuthenticatedPrincipal,
) -> AuthenticatedPrincipal:
    if not principal.email_verified:
        _forbidden("EMAIL_VERIFICATION_REQUIRED")
    return principal


def require_resource_owner(
    principal: AuthenticatedPrincipal,
    resource: Mapping[str, Any],
) -> None:
    if resource.get("owner_uid") != principal.uid:
        _forbidden()


def require_task_owner(
    principal: AuthenticatedPrincipal,
    task: Mapping[str, Any],
) -> None:
    require_resource_owner(principal, task)


def require_room_participant(
    principal: AuthenticatedPrincipal,
    room: Mapping[str, Any],
) -> None:
    participants = {str(item) for item in room.get("participant_uids", [])}
    if principal.uid not in participants or principal.uid in {
        str(item) for item in room.get("revoked_participant_uids", [])
    }:
        _forbidden()


def require_match_participant(
    principal: AuthenticatedPrincipal,
    match: Mapping[str, Any],
) -> None:
    if principal.uid not in {
        str(item) for item in match.get("participant_uids", [])
    }:
        _forbidden()


def require_admin(principal: AuthenticatedPrincipal) -> None:
    if not principal.admin:
        _forbidden()

