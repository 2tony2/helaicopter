"""Schemas for backend-owned Prefect orchestration responses."""

from __future__ import annotations

from helaicopter_api.schema.common import CamelCaseHttpResponseModel


class PrefectOatsMetadataResponse(CamelCaseHttpResponseModel):
    run_title: str | None = None
    source_path: str | None = None
    repo_root: str | None = None
    config_path: str | None = None
    local_metadata_path: str | None = None
    artifact_root: str | None = None


class PrefectDeploymentResponse(CamelCaseHttpResponseModel):
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


class PrefectWorkerResponse(CamelCaseHttpResponseModel):
    worker_id: str
    worker_name: str
    work_pool_name: str | None = None
    status: str | None = None
    last_heartbeat_at: str | None = None


class PrefectWorkPoolResponse(CamelCaseHttpResponseModel):
    work_pool_id: str
    work_pool_name: str
    type: str | None = None
    status: str | None = None
    is_paused: bool = False
    concurrency_limit: int | None = None
