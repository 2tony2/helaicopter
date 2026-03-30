"""Focused OAuth flow credential lifecycle tests."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Iterator
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
import pytest
import httpx
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from helaicopter_api.application import auth as auth_application
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.server.config import Settings
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app
from helaicopter_db.models.oltp import OltpBase


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


@contextmanager
def _oauth_client(*, settings: Settings | None = None) -> Iterator[TestClient]:
    application = create_app()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    OltpBase.metadata.create_all(engine)

    application.dependency_overrides[get_services] = lambda: _services_stub(
        sqlite_engine=engine,
        settings=settings or Settings(),
    )
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.dependency_overrides.clear()
        engine.dispose()
        auth_application._OAUTH_CLIENTS.clear()
        auth_application._PENDING_OAUTH_STATES.clear()


@dataclass
class _StubOAuthTokens:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scopes: list[str]


class _StubOAuthClient:
    def __init__(self) -> None:
        self.authorization_requests: list[tuple[str, str]] = []
        self.exchanged_codes: list[tuple[str, str]] = []
        self.refresh_requests: list[str] = []

    def build_authorization_url(self, *, state: str, code_challenge: str) -> str:
        self.authorization_requests.append((state, code_challenge))
        return (
            "https://example.test/oauth/authorize"
            f"?state={state}&challenge={code_challenge}"
        )

    def exchange_code(self, *, code: str, code_verifier: str) -> _StubOAuthTokens:
        self.exchanged_codes.append((code, code_verifier))
        return _StubOAuthTokens(
            access_token=f"access-for-{code}",
            refresh_token=f"refresh-for-{code_verifier[:8]}",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            scopes=["read", "write"],
        )

    def refresh_access_token(self, *, refresh_token: str) -> _StubOAuthTokens:
        self.refresh_requests.append(refresh_token)
        return _StubOAuthTokens(
            access_token=f"refreshed-{refresh_token}",
            refresh_token=f"{refresh_token}-next",
            expires_at=datetime.now(UTC) + timedelta(hours=2),
            scopes=["read", "write"],
        )


class _FailingRefreshOAuthClient(_StubOAuthClient):
    def refresh_access_token(self, *, refresh_token: str) -> _StubOAuthTokens:
        raise RuntimeError(f"refresh failed for {refresh_token}")

def test_initiate_oauth_returns_redirect_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HELA_CODEX_OAUTH_CLIENT_ID", "test-codex-client")

    with _oauth_client() as client:
        response = client.post("/auth/credentials/oauth/initiate", json={"provider": "codex"})
        assert response.status_code == 200
        payload = response.json()
        assert "redirectUrl" in payload
        parsed = urlparse(payload["redirectUrl"])
        state = parse_qs(parsed.query)["state"][0]
        assert state in auth_application._PENDING_OAUTH_STATES


def test_initiate_oauth_uses_registered_codex_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HELA_CODEX_OAUTH_CLIENT_ID", "test-codex-client")

    with _oauth_client() as client:
        response = client.post("/auth/credentials/oauth/initiate", json={"provider": "codex"})

        assert response.status_code == 200
        parsed = urlparse(response.json()["redirectUrl"])
        query = parse_qs(parsed.query)
        assert parsed.scheme == "https"
        assert parsed.netloc == "auth.openai.com"
        assert parsed.path == "/oauth/authorize"
        assert query["client_id"] == ["test-codex-client"]
        assert query["redirect_uri"] == ["http://127.0.0.1:31506/auth/credentials/oauth/callback"]
        assert query["response_type"] == ["code"]
        assert query["scope"] == ["openid profile email offline_access"]
        assert query["code_challenge_method"] == ["S256"]
        assert len(query["code_challenge"][0]) > 20
        assert len(query["state"][0]) > 20


def test_oauth_routes_use_request_scoped_codex_settings_instead_of_global_cache() -> None:
    settings = Settings(
        codex_oauth_client_id="request-scoped-client",
        codex_oauth_authorize_url="https://auth.example.test/oauth/authorize",
        codex_oauth_token_url="https://auth.example.test/oauth/token",
        codex_oauth_redirect_uri="http://127.0.0.1:43123/auth/callback",
        codex_oauth_scopes=("openid", "offline_access", "profile.custom"),
    )

    with _oauth_client(settings=settings) as client:
        initiate = client.post("/auth/credentials/oauth/initiate", json={"provider": "codex"})

        assert initiate.status_code == 200
        parsed = urlparse(initiate.json()["redirectUrl"])
        query = parse_qs(parsed.query)
        assert parsed.netloc == "auth.example.test"
        assert parsed.path == "/oauth/authorize"
        assert query["client_id"] == ["request-scoped-client"]
        assert query["redirect_uri"] == ["http://127.0.0.1:43123/auth/callback"]
        assert query["scope"] == ["openid offline_access profile.custom"]


def test_oauth_callback_returns_502_on_token_exchange_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HELA_CODEX_OAUTH_CLIENT_ID", "test-codex-client")
    request = httpx.Request("POST", "https://auth.openai.com/oauth/token")
    monkeypatch.setattr(
        auth_application.httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(500, request=request),
    )

    with _oauth_client() as client:
        initiate = client.post("/auth/credentials/oauth/initiate", json={"provider": "codex"})
        state = parse_qs(urlparse(initiate.json()["redirectUrl"]).query)["state"][0]
        response = client.get(f"/auth/credentials/oauth/callback?code=test_code&state={state}")

        assert response.status_code == 502
        assert response.json()["detail"] == "Codex OAuth token exchange failed"


def test_initiate_oauth_returns_400_for_claude() -> None:
    with _oauth_client() as client:
        response = client.post("/auth/credentials/oauth/initiate", json={"provider": "claude"})

        assert response.status_code == 400


def test_oauth_callback_stores_credential() -> None:
    with _oauth_client() as client:
        auth_application._OAUTH_CLIENTS["codex"] = _StubOAuthClient()
        initiate = client.post("/auth/credentials/oauth/initiate", json={"provider": "codex"})
        redirect_url = initiate.json()["redirectUrl"]
        state = parse_qs(urlparse(redirect_url).query)["state"][0]
        response = client.get(f"/auth/credentials/oauth/callback?code=test_code&state={state}")

        assert response.status_code == 200
        payload = response.json()
        assert payload["credentialId"].startswith("cred_")
        assert payload["status"] == "active"
        assert payload["tokenExpiresAt"] is not None


def test_codex_oauth_initiate_callback_and_refresh_use_configured_client_seam() -> None:
    oauth_client = _StubOAuthClient()

    with _oauth_client() as client:
        auth_application._OAUTH_CLIENTS["codex"] = oauth_client

        initiate = client.post("/auth/credentials/oauth/initiate", json={"provider": "codex"})
        assert initiate.status_code == 200
        initiate_payload = initiate.json()
        state = parse_qs(urlparse(initiate_payload["redirectUrl"]).query)["state"][0]
        pending = auth_application._PENDING_OAUTH_STATES[state]

        assert oauth_client.authorization_requests == [
            (state, auth_application._pkce_challenge(pending.code_verifier))
        ]

        callback = client.get(f"/auth/credentials/oauth/callback?code=codex-test-code&state={state}")
        assert callback.status_code == 200
        callback_payload = callback.json()
        assert oauth_client.exchanged_codes == [("codex-test-code", pending.code_verifier)]
        assert callback_payload["provider"] == "codex"
        assert callback_payload["credentialType"] == "oauth_token"
        assert callback_payload["providerStatusCode"] == "ready"
        assert callback_payload["providerStatusMessage"] == "Credential is ready for provider execution."

        refresh = client.post(f"/auth/credentials/{callback_payload['credentialId']}/refresh")
        assert refresh.status_code == 200
        refresh_payload = refresh.json()
        assert oauth_client.refresh_requests == [f"refresh-for-{pending.code_verifier[:8]}"]
        assert refresh_payload["status"] == "active"
        assert refresh_payload["providerStatusCode"] == "ready"
        assert refresh_payload["tokenExpiresAt"] is not None


def test_refresh_expired_token() -> None:
    with _oauth_client() as client:
        auth_application._OAUTH_CLIENTS["codex"] = _StubOAuthClient()
        create = client.post("/auth/credentials", json={
            "provider": "codex",
            "credentialType": "oauth_token",
            "accessToken": "expired-access",
            "refreshToken": "refresh-me",
            "tokenExpiresAt": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        })
        credential_id = create.json()["credentialId"]

        response = client.post(f"/auth/credentials/{credential_id}/refresh")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "active"
        assert payload["tokenExpiresAt"] is not None


def test_refresh_returns_502_on_token_exchange_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HELA_CODEX_OAUTH_CLIENT_ID", "test-codex-client")
    request = httpx.Request("POST", "https://auth.openai.com/oauth/token")
    monkeypatch.setattr(
        auth_application.httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(502, request=request),
    )

    with _oauth_client() as client:
        create = client.post("/auth/credentials", json={
            "provider": "codex",
            "credentialType": "oauth_token",
            "accessToken": "expired-access",
            "refreshToken": "refresh-me",
            "tokenExpiresAt": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        })
        credential_id = create.json()["credentialId"]

        response = client.post(f"/auth/credentials/{credential_id}/refresh")

        assert response.status_code == 502
        assert response.json()["detail"] == "Codex OAuth token exchange failed"


def test_refresh_transient_failure_does_not_mark_credential_expired() -> None:
    with _oauth_client() as client:
        auth_application._OAUTH_CLIENTS["codex"] = _FailingRefreshOAuthClient()
        create = client.post("/auth/credentials", json={
            "provider": "codex",
            "credentialType": "oauth_token",
            "accessToken": "still-active",
            "refreshToken": "refresh-me",
            "tokenExpiresAt": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        })
        credential_id = create.json()["credentialId"]

        response = client.post(f"/auth/credentials/{credential_id}/refresh")

        assert response.status_code == 502
        listing = client.get("/auth/credentials")
        credential = next(item for item in listing.json() if item["credentialId"] == credential_id)
        assert credential["status"] == "active"
