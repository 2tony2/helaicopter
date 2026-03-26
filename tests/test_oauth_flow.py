"""Focused OAuth flow and resolver credential lifecycle tests."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Iterator
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
import pytest
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from helaicopter_api.application import auth as auth_application
from helaicopter_api.application.dispatch import InMemoryWorkerRegistry
from helaicopter_api.application.resolver import ResolverLoop
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app
from helaicopter_db.models.oltp import OltpBase, WorkerRegistryRecord


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


@contextmanager
def _oauth_client() -> Iterator[TestClient]:
    application = create_app()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    OltpBase.metadata.create_all(engine)

    application.dependency_overrides[get_services] = lambda: _services_stub(sqlite_engine=engine)
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
    def build_authorization_url(self, *, state: str, code_challenge: str) -> str:
        return (
            "https://example.test/oauth/authorize"
            f"?state={state}&challenge={code_challenge}"
        )

    def exchange_code(self, *, code: str, code_verifier: str) -> _StubOAuthTokens:
        return _StubOAuthTokens(
            access_token=f"access-for-{code}",
            refresh_token=f"refresh-for-{code_verifier[:8]}",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            scopes=["read", "write"],
        )

    def refresh_access_token(self, *, refresh_token: str) -> _StubOAuthTokens:
        return _StubOAuthTokens(
            access_token=f"refreshed-{refresh_token}",
            refresh_token=f"{refresh_token}-next",
            expires_at=datetime.now(UTC) + timedelta(hours=2),
            scopes=["read", "write"],
        )


class _FailingRefreshOAuthClient(_StubOAuthClient):
    def refresh_access_token(self, *, refresh_token: str) -> _StubOAuthTokens:
        raise RuntimeError(f"refresh failed for {refresh_token}")


def _run(coro):  # noqa: ANN001, ANN202
    return asyncio.run(coro)


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


def test_resolver_auto_refreshes_expiring_token() -> None:
    @dataclass
    class Credential:
        credential_id: str
        provider: str
        credential_type: str
        status: str
        token_expires_at: datetime | None
        last_refreshed_at: datetime | None = None

    class InMemoryAuthStore:
        def __init__(self) -> None:
            self._credentials: dict[str, Credential] = {}

        def create(self, *, provider: str, credential_type: str, token_expires_at: datetime) -> Credential:
            credential = Credential(
                credential_id="cred_1",
                provider=provider,
                credential_type=credential_type,
                status="active",
                token_expires_at=token_expires_at,
            )
            self._credentials[credential.credential_id] = credential
            return credential

        def get(self, credential_id: str) -> Credential | None:
            return self._credentials.get(credential_id)

        def refresh_credential(self, credential_id: str) -> Credential:
            credential = self._credentials[credential_id]
            credential.last_refreshed_at = datetime.now(UTC)
            credential.token_expires_at = credential.last_refreshed_at + timedelta(hours=1)
            credential.status = "active"
            return credential

    auth_store = InMemoryAuthStore()
    credential = auth_store.create(
        provider="claude",
        credential_type="oauth_token",
        token_expires_at=datetime.now(UTC) + timedelta(minutes=3),
    )
    registry = InMemoryWorkerRegistry()
    registry.register(
        provider="claude",
        models=["claude-sonnet-4-6"],
        auth_credential_id=credential.credential_id,
    )

    resolver = ResolverLoop(
        registry=registry,
        auth_store=auth_store,
        graphs={},
        token_refresh_threshold=timedelta(minutes=5),
    )

    _run(resolver.tick())

    updated = auth_store.get(credential.credential_id)
    assert updated is not None
    assert updated.last_refreshed_at is not None


def test_resolver_marks_worker_auth_expired_when_refresh_fails() -> None:
    @dataclass
    class Credential:
        credential_id: str
        provider: str
        credential_type: str
        status: str
        token_expires_at: datetime | None

    class InMemoryAuthStore:
        def __init__(self) -> None:
            self._credentials = {
                "cred_1": Credential(
                    credential_id="cred_1",
                    provider="claude",
                    credential_type="oauth_token",
                    status="active",
                    token_expires_at=datetime.now(UTC) + timedelta(minutes=1),
                ),
            }

        def get(self, credential_id: str) -> Credential | None:
            return self._credentials.get(credential_id)

        def refresh_credential(self, credential_id: str) -> Credential:
            credential = self._credentials[credential_id]
            credential.status = "expired"
            raise RuntimeError("refresh failed")

    registry = InMemoryWorkerRegistry()
    worker = registry.register(
        provider="claude",
        models=["claude-sonnet-4-6"],
        auth_credential_id="cred_1",
    )
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    OltpBase.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            WorkerRegistryRecord(
                worker_id=worker.worker_id,
                worker_type="pi_shell",
                provider="claude",
                capabilities_json='{"provider":"claude","models":["claude-sonnet-4-6"]}',
                auth_credential_id="cred_1",
                host="local",
                pid=123,
                worktree_root=None,
                registered_at=datetime.now(UTC),
                last_heartbeat_at=datetime.now(UTC),
                status="idle",
                current_task_id=None,
                current_run_id=None,
                metadata_json=None,
            )
        )
        session.commit()

    resolver = ResolverLoop(
        registry=registry,
        auth_store=InMemoryAuthStore(),
        graphs={},
        token_refresh_threshold=timedelta(minutes=5),
        sqlite_engine=engine,
    )

    _run(resolver.tick())

    assert worker.status == "auth_expired"
    assert worker.auth_status == "expired"
    with Session(engine) as session:
        row = session.get(WorkerRegistryRecord, worker.worker_id)
        assert row is not None
        assert row.status == "auth_expired"
    engine.dispose()
