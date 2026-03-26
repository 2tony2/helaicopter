"""Operator-facing bootstrap and readiness summary."""

from __future__ import annotations

from collections import Counter

from helaicopter_api.application.auth import list_credentials
from helaicopter_api.application.provider_readiness import build_provider_readiness
from helaicopter_api.application.workers import list_workers
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.operator_bootstrap import (
    BootstrapReason,
    OperatorBootstrapResponse,
    ProviderBootstrapSummary,
)


_PROVIDERS = ("claude", "codex")

_REASON_MESSAGES = {
    "resolver_not_running": "The backend resolver loop is not running, so queued work will not dispatch.",
    "no_registered_workers": "No workers are registered with the control plane.",
    "missing_claude_worker": "Start at least one Claude worker to make Claude dispatch possible.",
    "missing_codex_worker": "Start at least one Codex worker to make Codex dispatch possible.",
    "auth_expired_workers": "Some registered workers have expired auth and need credential refresh.",
}

_REASON_NEXT_STEPS = {
    "resolver_not_running": "Restart the backend so the resolver loop starts polling again.",
    "no_registered_workers": "Register a Claude worker and a Codex worker from the Pi startup flow.",
    "missing_claude_worker": "Start or re-register a Claude-capable worker.",
    "missing_codex_worker": "Start or re-register a Codex-capable worker.",
    "auth_expired_workers": "Refresh the affected provider credential or local CLI session, then retry dispatch.",
}


def build_operator_bootstrap_summary(
    services: BackendServices,
    *,
    resolver_running: bool,
) -> OperatorBootstrapResponse:
    """Return a lightweight readiness summary for cold-start operator flow."""
    workers = list_workers(services.sqlite_engine)
    credentials = list_credentials(services.sqlite_engine)
    worker_counts = Counter(worker.provider for worker in workers)
    credential_counts = Counter(credential.provider for credential in credentials)

    blocking_reasons: list[BootstrapReason] = []
    if not resolver_running:
        blocking_reasons.append(_build_reason("resolver_not_running", severity="error"))
    if not workers:
        blocking_reasons.append(_build_reason("no_registered_workers", severity="error"))
    if worker_counts["claude"] == 0:
        blocking_reasons.append(_build_reason("missing_claude_worker", severity="warning"))
    if worker_counts["codex"] == 0:
        blocking_reasons.append(_build_reason("missing_codex_worker", severity="warning"))
    if any(worker.status == "auth_expired" for worker in workers):
        blocking_reasons.append(_build_reason("auth_expired_workers", severity="warning"))

    providers = [
        ProviderBootstrapSummary.model_validate(
            {
                "provider": provider,
                "status": build_provider_readiness(
                    provider=provider,
                    credentials=credentials,
                    workers=workers,
                ).status,
                "workerCount": worker_counts[provider],
                "credentialCount": credential_counts[provider],
                "blockingReasons": build_provider_readiness(
                    provider=provider,
                    credentials=credentials,
                    workers=workers,
                ).blocking_reasons,
            }
        )
        for provider in _PROVIDERS
    ]

    return OperatorBootstrapResponse(
        overall_status="ready" if not blocking_reasons else "blocked",
        resolver_running=resolver_running,
        blocking_reasons=blocking_reasons,
        providers=providers,
        total_worker_count=len(workers),
        total_credential_count=len(credentials),
        has_claude_worker=worker_counts["claude"] > 0,
        has_codex_worker=worker_counts["codex"] > 0,
    )


def _build_reason(code: str, *, severity: str) -> BootstrapReason:
    return BootstrapReason(
        code=code,
        severity=severity,
        message=_REASON_MESSAGES[code],
        next_step=_REASON_NEXT_STEPS.get(code),
    )
