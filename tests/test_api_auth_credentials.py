"""Endpoint tests for the auth credential store API."""

from __future__ import annotations

from contextlib import contextmanager
import json
from typing import Iterator
import subprocess

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
def _auth_client(*, settings: Settings | None = None) -> Iterator[TestClient]:
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
        settings=settings or Settings(),
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


def test_connect_claude_cli_creates_local_cli_session_credential(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    status_output = json.dumps(
        {
            "loggedIn": True,
            "authMethod": "claude.ai",
            "apiProvider": "firstParty",
            "email": "tony@naronadata.com",
            "orgId": "org_123",
            "orgName": "Narona",
            "subscriptionType": "max",
        }
    )

    def _fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args[0], 0, stdout=status_output, stderr="")

    with _auth_client(settings=Settings(claude_dir=claude_dir)) as client:
        monkeypatch.setattr(auth_application.subprocess, "run", _fake_run)
        response = client.post("/auth/credentials/claude-cli/connect")
        assert response.status_code == 201
        payload = response.json()
        assert payload["provider"] == "claude"
        assert payload["credentialType"] == "local_cli_session"
        assert payload["status"] == "active"
        assert payload["cliConfigPath"] == str(claude_dir)
        assert payload["subscriptionTier"] == "max"


def test_connect_claude_cli_uses_meaningful_credentials_blob_when_cli_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    claude_dir.joinpath("credentials.json").write_text(
        json.dumps(
            {
                "loggedIn": True,
                "authMethod": "claude.ai",
                "apiProvider": "firstParty",
                "email": "tony@naronadata.com",
                "orgId": "org_123",
                "orgName": "Narona",
                "subscriptionType": "max",
            }
        )
    )

    def _fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("claude not installed")

    with _auth_client(settings=Settings(claude_dir=claude_dir)) as client:
        monkeypatch.setattr(auth_application.subprocess, "run", _fake_run)
        response = client.post("/auth/credentials/claude-cli/connect")
        assert response.status_code == 201
        payload = response.json()
        assert payload["provider"] == "claude"
        assert payload["credentialType"] == "local_cli_session"
        assert payload["subscriptionTier"] == "max"


def test_connect_claude_cli_returns_400_when_auth_status_fails_and_dir_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    def _fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args[0],
            1,
            stdout="",
            stderr="not logged in",
        )

    with _auth_client(settings=Settings(claude_dir=claude_dir)) as client:
        monkeypatch.setattr(auth_application.subprocess, "run", _fake_run)
        response = client.post("/auth/credentials/claude-cli/connect")
        assert response.status_code == 400


def test_connect_claude_cli_rejects_empty_credentials_blob(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    claude_dir.joinpath("credentials.json").write_text("{}")

    def _fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("claude not installed")

    with _auth_client(settings=Settings(claude_dir=claude_dir)) as client:
        monkeypatch.setattr(auth_application.subprocess, "run", _fake_run)
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


def test_connect_claude_cli_revokes_duplicate_active_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    def _fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args[0], 0, stdout="", stderr="")

    with _auth_client(settings=Settings(claude_dir=claude_dir)) as client:
        monkeypatch.setattr(auth_application.subprocess, "run", _fake_run)
        first = client.post(
            "/auth/credentials",
            json={
                "provider": "claude",
                "credentialType": "local_cli_session",
                "cliConfigPath": "~/.claude/first",
            },
        )
        assert first.status_code == 201
        second = client.post(
            "/auth/credentials",
            json={
                "provider": "claude",
                "credentialType": "local_cli_session",
                "cliConfigPath": "~/.claude/second",
            },
        )
        assert second.status_code == 201

        response = client.post("/auth/credentials/claude-cli/connect")
        assert response.status_code == 201

        all_credentials = client.get("/auth/credentials").json()
        active_claude_cli_credentials = [
            item
            for item in all_credentials
            if item["provider"] == "claude" and item["credentialType"] == "local_cli_session" and item["status"] == "active"
        ]
        assert len(active_claude_cli_credentials) == 1
        revoked_claude_cli_credentials = [
            item
            for item in all_credentials
            if item["provider"] == "claude"
            and item["credentialType"] == "local_cli_session"
            and item["status"] == "revoked"
        ]
        assert len(revoked_claude_cli_credentials) == 1


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
