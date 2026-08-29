"""Firebase authentication and centralized authorization boundaries."""

from pairpilot_orchestrator.auth.authorization import (
    require_admin,
    require_match_participant,
    require_resource_owner,
    require_room_participant,
    require_task_owner,
    require_verified_email,
)
from pairpilot_orchestrator.auth.dependencies import (
    require_authenticated_user,
    require_internal_worker,
)
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal

__all__ = [
    "AuthenticatedPrincipal",
    "require_admin",
    "require_authenticated_user",
    "require_internal_worker",
    "require_match_participant",
    "require_resource_owner",
    "require_room_participant",
    "require_task_owner",
    "require_verified_email",
]
