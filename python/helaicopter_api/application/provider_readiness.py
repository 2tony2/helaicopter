"""Provider-level readiness model for real worker execution."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.engine import Engine

from helaicopter_api.application.auth import (
    CredentialProviderStatus,
    credential_is_provider_active,
    credential_provider_status_from_response,
    list_credentials,
)
from helaicopter_api.application.dispatch import RegisteredWorker
from helaicopter_api.schema.auth import CredentialResponse
from helaicopter_api.schema.provider_readiness import ProviderBlockingReason, ProviderReadinessResponse


def build_provider_readiness(
    *,
    provider: str,
    credentials: list[CredentialResponse],
    workers: list[object],
) -> ProviderReadinessResponse:
    provider_credentials = [item for item in credentials if item.provider == provider]
    provider_workers = [item for item in workers if getattr(item, "provider", None) == provider]
    expected_credential_type = _expected_credential_type(provider)
    active_credential_count = sum(
        1
        for credential in provider_credentials
        if credential.credential_type == expected_credential_type and credential_is_provider_active(credential)
    )
    healthy_worker_count = sum(1 for worker in provider_workers if getattr(worker, "status", None) != "dead")
    ready_worker_count = sum(
        1
        for worker in provider_workers
        if getattr(worker, "status", None) == "idle" and _worker_auth_status(worker) != "expired"
    )

    blocking_reasons: list[ProviderBlockingReason] = []
    if active_credential_count == 0:
        credential_issue = _provider_credential_issue(provider=provider, credentials=provider_credentials)
        blocking_reasons.append(
            ProviderBlockingReason(
                code=credential_issue.code if credential_issue is not None else _missing_auth_code(provider),
                message=(
                    credential_issue.message
                    if credential_issue is not None
                    else _missing_auth_message(provider)
                ),
            )
        )
    if healthy_worker_count == 0:
        blocking_reasons.append(
            ProviderBlockingReason(
                code="missing_worker",
                message=f"No healthy {provider} worker is registered.",
            )
        )

    if blocking_reasons:
        status = "blocked"
    elif ready_worker_count == 0:
        status = "degraded"
    else:
        status = "ready"

    return ProviderReadinessResponse(
        provider=provider,
        status=status,
        healthy_worker_count=healthy_worker_count,
        ready_worker_count=ready_worker_count,
        active_credential_count=active_credential_count,
        blocking_reasons=blocking_reasons,
    )


def _worker_auth_status(worker: object) -> str:
    auth_status = getattr(worker, "auth_status", None)
    if isinstance(auth_status, str):
        return auth_status
    return "expired" if getattr(worker, "status", None) == "auth_expired" else "valid"


def _provider_credential_issue(
    *,
    provider: str,
    credentials: list[CredentialResponse],
) -> CredentialProviderStatus | None:
    expected_credential_type = _expected_credential_type(provider)
    credential = next(
        (
            item
            for item in credentials
            if item.credential_type == expected_credential_type and not credential_is_provider_active(item)
        ),
        None,
    )
    if credential is not None:
        return credential_provider_status_from_response(credential)
    return None


def _expected_credential_type(provider: str) -> str:
    if provider == "claude":
        return "local_cli_session"
    if provider == "codex":
        return "oauth_token"
    return "credential"


def _missing_auth_code(provider: str) -> str:
    if provider == "claude":
        return "missing_cli_session"
    if provider == "codex":
        return "missing_credential"
    return "missing_credential"


def _missing_auth_message(provider: str) -> str:
    if provider == "claude":
        return "No valid local Claude CLI session is available."
    if provider == "codex":
        return "No valid Codex OAuth credential is available."
    return f"No active {provider} credential is available."


def build_provider_readiness_from_store(
    *,
    provider: str,
    engine: Engine | None,
    workers: list[RegisteredWorker],
) -> ProviderReadinessResponse | None:
    if engine is None:
        return None
    credentials = list_credentials(engine)
    known_provider = provider in {"claude", "codex"}
    has_provider_credentials = any(item.provider == provider for item in credentials)
    if not known_provider and not has_provider_credentials:
        return None
    return build_provider_readiness(provider=provider, credentials=credentials, workers=workers)
