"""Schemas for backend-owned Prefect orchestration responses."""

from __future__ import annotations

from helaicopter_api.schema.common import CamelCaseHttpResponseModel


class PrefectOatsMetadataResponse(CamelCaseHttpResponseModel):
    """OATS-specific metadata attached to a Prefect deployment or flow run."""

    run_title: str | None = None
    source_path: str | None = None
    repo_root: str | None = None
    config_path: str | None = None
    local_metadata_path: str | None = None
    artifact_root: str | None = None


class PrefectDeploymentResponse(CamelCaseHttpResponseModel):
    """Prefect deployment record with optional OATS metadata."""

    deployment_id: str
    deployment_name: str
    flow_id: str | None = None
    flow_name: str | None = None
    work_pool_name: str | None = None
    work_queue_name: str | None = None
    status: str | None = None
    updated_at: str | None = None
    tags: list[str] = []
    oats_metadata: PrefectOatsMetadataResponse | None = None


class PrefectFlowRunResponse(CamelCaseHttpResponseModel):
    """Prefect flow run record with state, deployment linkage, and optional OATS analytics."""

    flow_run_id: str
    flow_run_name: str | None = None
    deployment_id: str | None = None
    deployment_name: str | None = None
    flow_id: str | None = None
    flow_name: str | None = None
    work_pool_name: str | None = None
    work_queue_name: str | None = None
    state_type: str | None = None
    state_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    oats_metadata: PrefectOatsMetadataResponse | None = None
    analytics: "PrefectFlowRunAnalyticsResponse | None" = None


class PrefectFlowRunAnalyticsResponse(CamelCaseHttpResponseModel):
    """Task-level analytics summary for a Prefect flow run."""

    run_status: str
    task_count: int = 0
    completed_task_count: int = 0
    running_task_count: int = 0
    failed_task_count: int = 0
    task_attempt_count: int = 0
    last_updated_at: str | None = None


class PrefectWorkerResponse(CamelCaseHttpResponseModel):
    """Prefect worker record with heartbeat and work pool association."""

    worker_id: str
    worker_name: str
    work_pool_name: str | None = None
    status: str | None = None
    last_heartbeat_at: str | None = None


class PrefectWorkPoolResponse(CamelCaseHttpResponseModel):
    """Prefect work pool record with type, status, and concurrency configuration."""

    work_pool_id: str
    work_pool_name: str
    type: str | None = None
    status: str | None = None
    is_paused: bool = False
    concurrency_limit: int | None = None
