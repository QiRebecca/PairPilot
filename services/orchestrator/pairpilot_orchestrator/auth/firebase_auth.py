"""Firebase Admin SDK token verification using Cloud Run ADC."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

import firebase_admin  # type: ignore[import-untyped]
from firebase_admin import auth

from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal


class AuthenticationError(Exception):
    """A deliberately non-enumerating authentication failure."""


class AuthTokenVerifier(Protocol):
    async def verify(self, token: str) -> AuthenticatedPrincipal:
        """Verify a Firebase ID token and return its principal."""


def _firebase_app() -> firebase_admin.App:
    try:
        return firebase_admin.get_app()
    except ValueError:
        return firebase_admin.initialize_app()


class FirebaseAdminTokenVerifier:
    """Production verifier; revocation checks also reject disabled users."""

    async def verify(self, token: str) -> AuthenticatedPrincipal:
        try:
            claims = await asyncio.to_thread(
                auth.verify_id_token,
                token,
                _firebase_app(),
                True,
            )
            return AuthenticatedPrincipal.from_claims(dict(claims))
        except (
            auth.InvalidIdTokenError,
            auth.ExpiredIdTokenError,
            auth.RevokedIdTokenError,
            auth.UserDisabledError,
            ValueError,
        ) as exc:
            raise AuthenticationError("invalid authentication session") from exc


def public_firebase_config() -> dict[str, Any]:
    """Return non-secret browser configuration from runtime environment."""

    import os

    mapping = {
        "apiKey": "PAIRPILOT_FIREBASE_API_KEY",
        "authDomain": "PAIRPILOT_FIREBASE_AUTH_DOMAIN",
        "projectId": "GOOGLE_CLOUD_PROJECT",
        "appId": "PAIRPILOT_FIREBASE_APP_ID",
        "messagingSenderId": "PAIRPILOT_FIREBASE_MESSAGING_SENDER_ID",
    }
    return {
        public: os.getenv(environment, "")
        for public, environment in mapping.items()
    }
