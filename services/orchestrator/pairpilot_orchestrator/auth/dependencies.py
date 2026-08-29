"""FastAPI dependencies for Firebase Bearer authentication."""

from __future__ import annotations

import asyncio
import os
from typing import Annotated, cast

from fastapi import Header, HTTPException, Request
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token as google_id_token

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


async def require_internal_worker(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Verify the short-lived Google OIDC token used by Pub/Sub push."""

    if authorization is None:
        raise _unauthorized()
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized()
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    audience = os.getenv(
        "PAIRPILOT_INTERNAL_AUDIENCE",
        os.getenv("PAIRPILOT_PUBLIC_BASE_URL", ""),
    )
    expected_email = f"pairpilot-runtime@{project_id}.iam.gserviceaccount.com"
    if not project_id or not audience:
        raise _unauthorized()
    try:
        claims = await asyncio.to_thread(
            google_id_token.verify_oauth2_token,
            token.strip(),
            GoogleAuthRequest(),
            audience,
        )
    except (ValueError, TypeError) as exc:
        raise _unauthorized() from exc
    if (
        claims.get("email") != expected_email
        or claims.get("email_verified") is not True
    ):
        raise _unauthorized()
    return expected_email
