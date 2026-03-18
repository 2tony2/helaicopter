"""Schemas for OATS orchestration runs and DAG views."""

from __future__ import annotations

from typing import Literal

from helaicopter_domain.ids import RunId, SessionId, TaskId
from helaicopter_domain.paths import EncodedProjectKey
from helaicopter_domain.vocab import ProviderName, RunRuntimeStatus, TaskRuntimeStatus
from helaicopter_api.schema.common import CamelCaseHttpResponseModel


class OrchestrationInvocationResponse(CamelCaseHttpResponseModel):
    """Agent invocation snapshot."""

    agent: ProviderName
    role: str
    command: list[str]
    cwd: str
    prompt: str
    session_id: SessionId | None = None
    output_text: str = ""
    raw_stdout: str = ""
    raw_stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False
    started_at: str
    finished_at: str | None = None
    project_path: EncodedProjectKey | None = None
    conversation_path: str | None = None


class OrchestrationTaskResponse(CamelCaseHttpResponseModel):
    """A single task within an orchestration run."""

    task_id: TaskId
    title: str
    depends_on: list[str] = []
    status: TaskRuntimeStatus
    attempts: int = 0
    invocation: OrchestrationInvocationResponse | None = None


class OrchestrationDagNodeResponse(CamelCaseHttpResponseModel):
    id: str
    kind: Literal["planner", "task"]
    label: str
    description: str | None = None
    role: str
    agent: ProviderName
    session_id: SessionId | None = None
    project_path: EncodedProjectKey | None = None
    conversation_path: str | None = None
    status: TaskRuntimeStatus | RunRuntimeStatus
    is_active: bool = False
    attempts: int | None = None
    last_heartbeat_at: str | None = None
    exit_code: int | None = None
    timed_out: bool = False
    depth: int = 0


class OrchestrationDagEdgeResponse(CamelCaseHttpResponseModel):
    id: str
    source: str
    target: str
    label: str | None = None


class OrchestrationDagStatsResponse(CamelCaseHttpResponseModel):
    total_nodes: int = 0
    total_edges: int = 0
    max_depth: int = 0
    max_breadth: int = 0
    root_count: int = 0
    provider_breakdown: dict[ProviderName, int] = {}
    timed_out_count: int = 0
    active_count: int = 0
    pending_count: int = 0
    failed_count: int = 0
    succeeded_count: int = 0


class OrchestrationDagResponse(CamelCaseHttpResponseModel):
    nodes: list[OrchestrationDagNodeResponse] = []
    edges: list[OrchestrationDagEdgeResponse] = []
    stats: OrchestrationDagStatsResponse


class OrchestrationRunResponse(CamelCaseHttpResponseModel):
    """Full orchestration run record."""

    source: Literal["overnight-oats"] = "overnight-oats"
    contract_version: str
    run_id: RunId
    run_title: str
    repo_root: str
    config_path: str
    run_spec_path: str
    mode: str
    integration_branch: str
    task_pr_target: str
    final_pr_target: str
    status: RunRuntimeStatus
    active_task_id: TaskId | None = None
    heartbeat_at: str | None = None
    finished_at: str | None = None
    planner: OrchestrationInvocationResponse | None = None
    tasks: list[OrchestrationTaskResponse] = []
    created_at: str
    last_updated_at: str
    is_running: bool = False
    recorded_at: str
    record_path: str
    dag: OrchestrationDagResponse
