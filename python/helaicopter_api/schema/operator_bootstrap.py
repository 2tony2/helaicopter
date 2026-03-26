"""Schemas for operator bootstrap readiness."""

from __future__ import annotations

from helaicopter_api.schema.common import CamelCaseHttpResponseModel
from helaicopter_api.schema.provider_readiness import ProviderBlockingReason


class BootstrapReason(CamelCaseHttpResponseModel):
    """Machine-readable explanation for why the system is not ready."""

    code: str
    severity: str
    message: str
    next_step: str | None = None


class ProviderBootstrapSummary(CamelCaseHttpResponseModel):
    """Provider-specific worker and credential counts."""

    provider: str
    status: str = "unknown"
    worker_count: int = 0
    credential_count: int = 0
    blocking_reasons: list[ProviderBlockingReason] = []


class OperatorBootstrapResponse(CamelCaseHttpResponseModel):
    """Cold-start readiness summary for the operator console."""

    overall_status: str
    resolver_running: bool
    blocking_reasons: list[BootstrapReason]
    providers: list[ProviderBootstrapSummary]
    total_worker_count: int = 0
    total_credential_count: int = 0
    has_claude_worker: bool = False
    has_codex_worker: bool = False
