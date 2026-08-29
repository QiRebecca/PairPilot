"""Typed identity extracted only from a verified Firebase ID token."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """The authoritative browser principal for one protected request."""

    uid: str
    email: str | None
    email_verified: bool
    admin: bool = False

    @classmethod
    def from_claims(cls, claims: dict[str, Any]) -> AuthenticatedPrincipal:
        uid = str(claims.get("uid") or claims.get("sub") or "").strip()
        if not uid:
            raise ValueError("verified token is missing a UID")
        email_value = claims.get("email")
        email = str(email_value) if email_value else None
        return cls(
            uid=uid,
            email=email,
            email_verified=claims.get("email_verified") is True,
            admin=claims.get("admin") is True,
        )
