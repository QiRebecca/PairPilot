"""FastAPI dependencies for Firebase Bearer authentication."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Header, HTTPException, Request

from pairpilot_orchestrator.auth.firebase_auth import (
    AuthenticationError,
    AuthTokenVerifier,
    FirebaseAdminTokenVerifier,
)
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail={"code": "AUTHENTICATION_REQUIRED", "message": "Sign in again."},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_authenticated_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedPrincipal:
    if authorization is None:
        raise _unauthorized()
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized()
    verifier_value = getattr(request.app.state, "auth_token_verifier", None)
    verifier = cast(
        AuthTokenVerifier,
        verifier_value if verifier_value is not None else FirebaseAdminTokenVerifier(),
    )
    try:
        return await verifier.verify(token.strip())
    except AuthenticationError as exc:
        raise _unauthorized() from exc

