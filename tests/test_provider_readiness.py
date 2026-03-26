from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from helaicopter_api.application import auth as auth_application
from helaicopter_api.application.auth import create_credential, list_credentials, refresh_credential
from helaicopter_api.application.dispatch import InMemoryWorkerRegistry
from helaicopter_api.schema.auth import CreateCredentialRequest
from helaicopter_api.server.config import Settings
from helaicopter_db.models.oltp import OltpBase


def _engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    OltpBase.metadata.create_all(engine)
    return engine


def test_claude_provider_is_ready_when_cli_session_and_worker_exist() -> None:
    from helaicopter_api.application.provider_readiness import build_provider_readiness

    engine = _engine()
    try:
        create_credential(
            engine,
            CreateCredentialRequest.model_validate(
                {
                    "provider": "claude",
                    "credentialType": "local_cli_session",
                    "cliConfigPath": "~/.claude",
                }
            ),
        )
        registry = InMemoryWorkerRegistry()
        registry.register(provider="claude", models=["claude-sonnet-4-6"])

        readiness = build_provider_readiness(
            provider="claude",
            credentials=list_credentials(engine),
            workers=registry.all_workers(),
        )

        assert readiness.provider == "claude"
        assert readiness.status == "ready"
        assert readiness.active_credential_count == 1
        assert readiness.ready_worker_count == 1
    finally:
        engine.dispose()


def test_codex_provider_is_ready_when_oauth_token_and_worker_exist() -> None:
    from helaicopter_api.application.provider_readiness import build_provider_readiness

    engine = _engine()
    try:
        create_credential(
            engine,
            CreateCredentialRequest.model_validate(
                {
                    "provider": "codex",
                    "credentialType": "oauth_token",
                    "accessToken": "token-1",
                    "refreshToken": "refresh-1",
                    "tokenExpiresAt": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                }
            ),
        )
        registry = InMemoryWorkerRegistry()
        registry.register(provider="codex", models=["o3-pro"])

        readiness = build_provider_readiness(
            provider="codex",
            credentials=list_credentials(engine),
            workers=registry.all_workers(),
        )

        assert readiness.status == "ready"
        assert readiness.ready_worker_count == 1
        assert readiness.active_credential_count == 1
    finally:
        engine.dispose()


def test_provider_readiness_explains_missing_auth_and_missing_worker_separately() -> None:
    from helaicopter_api.application.provider_readiness import build_provider_readiness

    readiness = build_provider_readiness(
        provider="codex",
        credentials=[],
        workers=[],
    )

    assert readiness.status == "blocked"
    assert len(readiness.blocking_reasons) == 2
    assert readiness.blocking_reasons[0].code == "missing_credential"
    assert readiness.blocking_reasons[0].message == "No valid Codex OAuth credential is available."
    assert "worker" in readiness.blocking_reasons[1].message.lower()


def test_claude_local_cli_session_credential_without_config_is_not_provider_ready() -> None:
    from helaicopter_api.application.provider_readiness import build_provider_readiness

    engine = _engine()
    try:
        create_credential(
            engine,
            CreateCredentialRequest.model_validate(
                {
                    "provider": "claude",
                    "credentialType": "local_cli_session",
                }
            ),
        )

        readiness = build_provider_readiness(
            provider="claude",
            credentials=list_credentials(engine),
            workers=[],
        )

        assert readiness.status == "blocked"
        assert readiness.blocking_reasons[0].code == "missing_cli_session"
    finally:
        engine.dispose()


def test_mismatched_invalid_credentials_are_normalized_by_provider() -> None:
    from helaicopter_api.application.provider_readiness import build_provider_readiness

    engine = _engine()
    try:
        create_credential(
            engine,
            CreateCredentialRequest.model_validate(
                {
                    "provider": "codex",
                    "credentialType": "local_cli_session",
                }
            ),
        )
        create_credential(
            engine,
            CreateCredentialRequest.model_validate(
                {
                    "provider": "claude",
                    "credentialType": "oauth_token",
                    "accessToken": "token-1",
                    "refreshToken": "refresh-1",
                    "tokenExpiresAt": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
                }
            ),
        )

        codex_readiness = build_provider_readiness(
            provider="codex",
            credentials=list_credentials(engine),
            workers=[],
        )
        claude_readiness = build_provider_readiness(
            provider="claude",
            credentials=list_credentials(engine),
            workers=[],
        )

        assert codex_readiness.blocking_reasons[0].code == "missing_credential"
        assert codex_readiness.blocking_reasons[0].message == "No valid Codex OAuth credential is available."
        assert claude_readiness.blocking_reasons[0].code == "missing_cli_session"
        assert claude_readiness.blocking_reasons[0].message == "No valid local Claude CLI session is available."
    finally:
        engine.dispose()


def test_refresh_failed_oauth_credential_is_persisted_as_expired() -> None:
    class FailingOAuthClient:
        def build_authorization_url(self, *, state: str, code_challenge: str) -> str:
            return "https://example.test/oauth"

        def exchange_code(self, *, code: str, code_verifier: str):
            raise AssertionError("not used")

        def refresh_access_token(self, *, refresh_token: str):
            raise RuntimeError("refresh failed")

    engine = _engine()
    previous_client = auth_application._OAUTH_CLIENTS.get("claude")
    auth_application._OAUTH_CLIENTS["claude"] = FailingOAuthClient()
    try:
        credential = create_credential(
            engine,
            CreateCredentialRequest.model_validate(
                {
                    "provider": "claude",
                    "credentialType": "oauth_token",
                    "accessToken": "token-1",
                    "refreshToken": "refresh-1",
                    "tokenExpiresAt": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
                }
            ),
        )

        with pytest.raises(RuntimeError, match="refresh failed"):
            refresh_credential(engine, credential.credential_id, settings=Settings())

        refreshed = [item for item in list_credentials(engine) if item.credential_id == credential.credential_id][0]
        assert refreshed.status == "expired"
    finally:
        if previous_client is None:
            auth_application._OAUTH_CLIENTS.pop("claude", None)
        else:
            auth_application._OAUTH_CLIENTS["claude"] = previous_client
        engine.dispose()
