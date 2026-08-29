from __future__ import annotations

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pairpilot_orchestrator.auth.authorization import (
    require_resource_owner,
    require_room_participant,
    require_verified_email,
)
from pairpilot_orchestrator.auth.dependencies import require_authenticated_user
from pairpilot_orchestrator.auth.firebase_auth import AuthenticationError
from pairpilot_orchestrator.auth.principal import AuthenticatedPrincipal


class FakeVerifier:
    async def verify(self, token: str) -> AuthenticatedPrincipal:
        principals = {
            "user-a": AuthenticatedPrincipal(
                uid="uid-a", email="a@example.test", email_verified=True
            ),
            "user-b": AuthenticatedPrincipal(
                uid="uid-b", email="b@example.test", email_verified=True
            ),
            "unverified": AuthenticatedPrincipal(
                uid="uid-u", email="u@example.test", email_verified=False
            ),
        }
        if token in {"expired", "disabled", "malformed"}:
            raise AuthenticationError("provider rejected token")
        try:
            return principals[token]
        except KeyError as exc:
            raise AuthenticationError("provider rejected token") from exc


def auth_app() -> FastAPI:
    app = FastAPI()
    app.state.auth_token_verifier = FakeVerifier()

    @app.get("/private")
    async def private(
        principal: Annotated[
            AuthenticatedPrincipal, Depends(require_authenticated_user)
        ],
    ) -> dict[str, str]:
        return {"uid": principal.uid}

    @app.get("/verified")
    async def verified(
        principal: Annotated[
            AuthenticatedPrincipal, Depends(require_authenticated_user)
        ],
    ) -> dict[str, str]:
        require_verified_email(principal)
        return {"uid": principal.uid}

    return app


@pytest.mark.parametrize(
    "header",
    [None, "", "Basic abc", "Bearer", "Bearer expired", "Bearer disabled"],
)
def test_auth_dependency_rejects_missing_malformed_expired_and_disabled_tokens(
    header: str | None,
) -> None:
    headers = {"Authorization": header} if header else {}
    response = TestClient(auth_app()).get("/private", headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"


def test_auth_dependency_attaches_authoritative_principal() -> None:
    response = TestClient(auth_app()).get(
        "/private", headers={"Authorization": "Bearer user-a"}
    )
    assert response.status_code == 200
    assert response.json() == {"uid": "uid-a"}


def test_unverified_user_is_blocked_from_verified_action() -> None:
    response = TestClient(auth_app()).get(
        "/verified", headers={"Authorization": "Bearer unverified"}
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "EMAIL_VERIFICATION_REQUIRED"


def test_cross_user_owner_and_room_checks_return_generic_403() -> None:
    user_a = AuthenticatedPrincipal(
        uid="uid-a", email="a@example.test", email_verified=True
    )
    with pytest.raises(HTTPException) as owner_error:
        require_resource_owner(user_a, {"owner_uid": "uid-b", "private": "secret"})
    assert owner_error.value.status_code == 403
    assert "secret" not in str(owner_error.value.detail)

    with pytest.raises(HTTPException) as room_error:
        require_room_participant(
            user_a,
            {"participant_uids": ["uid-b"], "room_id": "room-private"},
        )
    assert room_error.value.status_code == 403
    assert "room-private" not in str(room_error.value.detail)
