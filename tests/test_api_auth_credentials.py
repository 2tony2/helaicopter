"""Endpoint tests for the auth credential store API."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from helaicopter_api.application import auth as auth_application
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.config import Settings
from helaicopter_api.server.main import create_app
from helaicopter_db.models.oltp import OltpBase


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


@contextmanager
def _auth_client() -> Iterator[TestClient]:
    """Test client with an in-memory SQLite engine for auth credential tests."""
    application = create_app()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    OltpBase.metadata.create_all(engine)

    application.dependency_overrides[get_services] = lambda: _services_stub(
        sqlite_engine=engine,
        settings=Settings(),
    )
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.dependency_overrides.clear()
        engine.dispose()


def _create_api_key_credential(client: TestClient, **overrides: object) -> str:
    payload = {
        "provider": "claude",
        "credentialType": "api_key",
        "apiKey": "sk-ant-test-key",
        **overrides,
    }
    response = client.post("/auth/credentials", json=payload)
    assert response.status_code == 201
    return response.json()["credentialId"]


# ---- Create ----


def test_create_api_key_credential() -> None:
    with _auth_client() as client:
        response = client.post("/auth/credentials", json={
            "provider": "claude",
            "credentialType": "api_key",
            "apiKey": "sk-ant-test-key",
        })
        assert response.status_code == 201
        payload = response.json()
        assert payload["credentialId"].startswith("cred_")
        assert payload["status"] == "active"
        # API key must not be returned in cleartext
        assert "apiKey" not in payload


def test_create_oauth_token_credential_with_expiry() -> None:
    with _auth_client() as client:
        response = client.post("/auth/credentials", json={
            "provider": "codex",
            "credentialType": "oauth_token",
            "accessToken": "fake-token",
            "tokenExpiresAt": "2026-04-01T00:00:00Z",
        })
        assert response.status_code == 201
        payload = response.json()
        assert payload["tokenExpiresAt"] is not None


def test_create_local_cli_session_credential() -> None:
    with _auth_client() as client:
        response = client.post("/auth/credentials", json={
            "provider": "claude",
            "credentialType": "local_cli_session",
            "cliConfigPath": "~/.claude",
        })
        assert response.status_code == 201
        payload = response.json()
        assert payload["credentialType"] == "local_cli_session"
        assert payload["status"] == "active"


def test_connect_claude_cli_creates_local_cli_session_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        auth_application,
        "discover_claude_cli_session",
        lambda *, settings: auth_application.ClaudeCliSession(cli_config_path="~/.claude"),
    )

    with _auth_client() as client:
        response = client.post("/auth/credentials/claude-cli/connect")
        assert response.status_code == 201
        payload = response.json()
        assert payload["provider"] == "claude"
        assert payload["credentialType"] == "local_cli_session"
        assert payload["status"] == "active"


def test_connect_claude_cli_returns_400_when_not_authenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*, settings: object) -> auth_application.ClaudeCliSession:
        raise ValueError("Claude CLI is not authenticated")

    monkeypatch.setattr(auth_application, "discover_claude_cli_session", _raise)

    with _auth_client() as client:
        response = client.post("/auth/credentials/claude-cli/connect")
        assert response.status_code == 400


def test_connect_claude_cli_reuses_existing_active_credential(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        auth_application,
        "discover_claude_cli_session",
        lambda *, settings: auth_application.ClaudeCliSession(cli_config_path="~/.claude/reused"),
    )

    with _auth_client() as client:
        created = client.post(
            "/auth/credentials",
            json={
                "provider": "claude",
                "credentialType": "local_cli_session",
                "cliConfigPath": "~/.claude/original",
            },
        )
        assert created.status_code == 201
        credential_id = created.json()["credentialId"]

        response = client.post("/auth/credentials/claude-cli/connect")
        assert response.status_code == 201
        payload = response.json()
        assert payload["credentialId"] == credential_id
        assert payload["cliConfigPath"] == "~/.claude/reused"

        all_credentials = client.get("/auth/credentials").json()
        active_claude_cli_credentials = [
            item
            for item in all_credentials
            if item["provider"] == "claude" and item["credentialType"] == "local_cli_session" and item["status"] == "active"
        ]
        assert len(active_claude_cli_credentials) == 1


# ---- List ----


def test_list_credentials_shows_status_not_secrets() -> None:
    with _auth_client() as client:
        _create_api_key_credential(client, provider="claude")
        _create_api_key_credential(client, provider="codex", apiKey="sk-codex-key")
        response = client.get("/auth/credentials")
        creds = response.json()
        assert len(creds) == 2
        for c in creds:
            assert "accessToken" not in c
            assert "apiKey" not in c
            assert "status" in c


# ---- Revoke ----


def test_revoke_credential_sets_status() -> None:
    with _auth_client() as client:
        cred_id = _create_api_key_credential(client)
        response = client.delete(f"/auth/credentials/{cred_id}")
        assert response.status_code == 200
        # Verify status
        response = client.get("/auth/credentials")
        cred = [c for c in response.json() if c["credentialId"] == cred_id][0]
        assert cred["status"] == "revoked"


# ---- Cost tracking ----


def test_record_cost_updates_cumulative() -> None:
    with _auth_client() as client:
        cred_id = _create_api_key_credential(client)
        response = client.post(f"/auth/credentials/{cred_id}/record-cost", json={
            "costUsd": 1.50,
        })
        assert response.status_code == 200
        # Verify cumulative
        response = client.get("/auth/credentials")
        cred = [c for c in response.json() if c["credentialId"] == cred_id][0]
        assert cred["cumulativeCostUsd"] == 1.50


def test_record_cost_accumulates() -> None:
    with _auth_client() as client:
        cred_id = _create_api_key_credential(client)
        client.post(f"/auth/credentials/{cred_id}/record-cost", json={"costUsd": 1.0})
        client.post(f"/auth/credentials/{cred_id}/record-cost", json={"costUsd": 2.5})
        response = client.get("/auth/credentials")
        cred = [c for c in response.json() if c["credentialId"] == cred_id][0]
        assert cred["cumulativeCostUsd"] == 3.5


# ---- 404 cases ----


def test_revoke_unknown_credential_returns_404() -> None:
    with _auth_client() as client:
        response = client.delete("/auth/credentials/cred_nonexistent")
        assert response.status_code == 404


def test_record_cost_unknown_credential_returns_404() -> None:
    with _auth_client() as client:
        response = client.post("/auth/credentials/cred_nonexistent/record-cost", json={
            "costUsd": 1.0,
        })
        assert response.status_code == 404
