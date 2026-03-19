"""Port protocol and normalized backend-owned Prefect models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class PrefectOatsPayload:
    run_title: str | None = None
    source_path: str | None = None
    repo_root: str | None = None
    config_path: str | None = None


@dataclass(frozen=True, slots=True)
class PrefectDeploymentRecord:
    deployment_id: str
    deployment_name: str
    flow_id: str | None = None
    flow_name: str | None = None
    work_pool_name: str | None = None
    work_queue_name: str | None = None
    status: str | None = None
    updated_at: str | None = None
    tags: list[str] = field(default_factory=list)
    oats_payload: PrefectOatsPayload | None = None


@dataclass(frozen=True, slots=True)
class PrefectFlowRunRecord:
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


@dataclass(frozen=True, slots=True)
class PrefectWorkerRecord:
    worker_id: str
    worker_name: str
    work_pool_name: str | None = None
    status: str | None = None
    last_heartbeat_at: str | None = None


@dataclass(frozen=True, slots=True)
class PrefectWorkPoolRecord:
    work_pool_id: str
    work_pool_name: str
    type: str | None = None
    status: str | None = None
    is_paused: bool = False
    concurrency_limit: int | None = None


@runtime_checkable
class PrefectOrchestrationPort(Protocol):
    """Normalized read surface for Prefect orchestration state."""

    def list_deployments(self) -> list[PrefectDeploymentRecord]:
        ...

    def list_flow_runs(self) -> list[PrefectFlowRunRecord]:
        ...

    def read_flow_run(self, flow_run_id: str) -> PrefectFlowRunRecord:
        ...

    def list_workers(self) -> list[PrefectWorkerRecord]:
        ...

    def list_work_pools(self) -> list[PrefectWorkPoolRecord]:
        ...
