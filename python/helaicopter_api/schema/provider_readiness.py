"""Schemas for provider-level orchestration readiness."""

from __future__ import annotations

from helaicopter_api.schema.common import CamelCaseHttpResponseModel


class ProviderBlockingReason(CamelCaseHttpResponseModel):
    code: str
    message: str
    severity: str = "error"


class ProviderReadinessResponse(CamelCaseHttpResponseModel):
    provider: str
    status: str
    healthy_worker_count: int = 0
    ready_worker_count: int = 0
    active_credential_count: int = 0
    blocking_reasons: list[ProviderBlockingReason] = []
