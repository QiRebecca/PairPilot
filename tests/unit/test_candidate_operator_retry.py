from __future__ import annotations

import sys
from pathlib import Path

import pytest
import requests
from google.auth.exceptions import TransportError

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from seed_startup_v2_candidate_cohort import _admin_request, _sign_in  # noqa: E402


class _Response:
    status_code = 200


def test_admin_request_retries_oauth_transport_failure(monkeypatch) -> None:
    attempts = 0

    class Session:
        def request(self, method: str, url: str, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise TransportError("temporary OAuth timeout")
            assert kwargs["timeout"] == 45
            return _Response()

    monkeypatch.setattr("seed_startup_v2_candidate_cohort.time.sleep", lambda _: None)
    assert _admin_request(Session(), "GET", "https://example.invalid") is not None
    assert attempts == 3


def test_admin_request_surfaces_persistent_transport_failure(monkeypatch) -> None:
    attempts = 0

    class Session:
        def request(self, method: str, url: str, **kwargs):
            nonlocal attempts
            attempts += 1
            raise requests.ConnectTimeout("still unavailable")

    monkeypatch.setattr("seed_startup_v2_candidate_cohort.time.sleep", lambda _: None)
    with pytest.raises(requests.ConnectTimeout):
        _admin_request(Session(), "GET", "https://example.invalid")
    assert attempts == 4


def test_sign_in_retries_identity_toolkit_timeout(monkeypatch) -> None:
    attempts = 0

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return {"idToken": "test-token"}

    def post(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise requests.ReadTimeout("temporary Identity Toolkit timeout")
        assert kwargs["timeout"] == 45
        return Response()

    monkeypatch.setattr("seed_startup_v2_candidate_cohort.requests.post", post)
    monkeypatch.setattr("seed_startup_v2_candidate_cohort.time.sleep", lambda _: None)
    assert _sign_in("user@example.com", "password", "api-key") == "test-token"
    assert attempts == 2
