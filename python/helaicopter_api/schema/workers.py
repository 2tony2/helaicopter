"""Schemas for the worker registry API."""

from __future__ import annotations

from pydantic import BaseModel

from helaicopter_api.schema.common import CamelCaseHttpResponseModel, camel_case_request_config
from helaicopter_api.schema.provider_readiness import ProviderReadinessResponse


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class WorkerCapabilitiesPayload(BaseModel):
    """Capabilities advertised by a worker during registration."""

    model_config = camel_case_request_config(extra="forbid")

    provider: str
    models: list[str] = []
    max_concurrent_tasks: int = 1
    supports_discovery: bool = False
    supports_resume: bool = False
    tags: list[str] = []


class WorkerRegistrationRequest(BaseModel):
    """Body for ``POST /workers/register``."""

    model_config = camel_case_request_config(extra="forbid")

    worker_type: str
    provider: str
    capabilities: WorkerCapabilitiesPayload
    host: str = "local"
    pid: int | None = None
    worktree_root: str | None = None


class WorkerHeartbeatRequest(BaseModel):
    """Body for ``POST /workers/{worker_id}/heartbeat``."""

    model_config = camel_case_request_config(extra="forbid")

    status: str
    current_task_id: str | None = None
    current_run_id: str | None = None
    provider_session_id: str | None = None
    session_status: str | None = None
    session_started_at: str | None = None
    session_last_used_at: str | None = None
    session_failure_reason: str | None = None


class WorkerTaskReportRequest(BaseModel):
    """Body for ``POST /workers/{worker_id}/report``."""

    model_config = camel_case_request_config(extra="forbid")

    task_id: str
    attempt_id: str
    status: str
    duration_seconds: float
    branch_name: str | None = None
    commit_sha: str | None = None
    error_summary: str | None = None
    provider_session_id: str | None = None
    session_status: str | None = None
    session_started_at: str | None = None
    session_last_used_at: str | None = None
    session_failure_reason: str | None = None
    session_reused: bool = False


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class WorkerCapabilitiesResponse(CamelCaseHttpResponseModel):
    """Capabilities snapshot in a worker response."""

    provider: str
    models: list[str] = []
    max_concurrent_tasks: int = 1
    supports_discovery: bool = False
    supports_resume: bool = False
    tags: list[str] = []


class WorkerDetailResponse(CamelCaseHttpResponseModel):
    """Full detail for a single worker."""

    worker_id: str
    worker_type: str
    provider: str
    capabilities: WorkerCapabilitiesResponse
    host: str
    pid: int | None = None
    worktree_root: str | None = None
    registered_at: str
    last_heartbeat_at: str
    status: str
    readiness_reason: str | None = None
    current_task_id: str | None = None
    current_run_id: str | None = None
    provider_session_id: str | None = None
    session_status: str = "absent"
    session_started_at: str | None = None
    session_last_used_at: str | None = None
    session_failure_reason: str | None = None
    session_reset_available: bool = True
    session_reset_requested_at: str | None = None


class WorkerRegistrationResponse(CamelCaseHttpResponseModel):
    """Response for ``POST /workers/register``."""

    worker_id: str
    status: str


class WorkerProviderReadinessResponse(ProviderReadinessResponse):
    """Provider-level readiness payload exposed under the workers API."""
