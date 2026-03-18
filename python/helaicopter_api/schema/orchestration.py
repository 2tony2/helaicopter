"""Schemas for OATS orchestration runs and DAG views."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class OrchestrationCamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )


OrchestrationTaskStatus = Literal[
    "pending", "running", "succeeded", "failed", "timed_out", "skipped", "blocked"
]
OrchestrationRunStatus = Literal[
    "pending", "planning", "running", "completed", "failed", "timed_out"
]


class OrchestrationInvocationResponse(OrchestrationCamelModel):
    """Agent invocation snapshot."""

    agent: str
    role: str
    command: list[str]
    cwd: str
    prompt: str
    session_id: str | None = None
    output_text: str = ""
    raw_stdout: str = ""
    raw_stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False
    started_at: str
    finished_at: str | None = None
    project_path: str | None = None
    conversation_path: str | None = None


class OrchestrationTaskResponse(OrchestrationCamelModel):
    """A single task within an orchestration run."""

    task_id: str
    title: str
    depends_on: list[str] = Field(default_factory=list)
    status: OrchestrationTaskStatus
    attempts: int = 0
    invocation: OrchestrationInvocationResponse | None = None


class OrchestrationDagNodeResponse(OrchestrationCamelModel):
    id: str
    kind: Literal["planner", "task"]
    label: str
    description: str | None = None
    role: str
    agent: str
    session_id: str | None = None
    project_path: str | None = None
    conversation_path: str | None = None
    status: str
    is_active: bool = False
    attempts: int | None = None
    last_heartbeat_at: str | None = None
    exit_code: int | None = None
    timed_out: bool = False
    depth: int = 0


class OrchestrationDagEdgeResponse(OrchestrationCamelModel):
    id: str
    source: str
    target: str
    label: str | None = None


class OrchestrationDagStatsResponse(OrchestrationCamelModel):
    total_nodes: int = 0
    total_edges: int = 0
    max_depth: int = 0
    max_breadth: int = 0
    root_count: int = 0
    provider_breakdown: dict[str, int] = Field(default_factory=dict)
    timed_out_count: int = 0
    active_count: int = 0
    pending_count: int = 0
    failed_count: int = 0
    succeeded_count: int = 0


class OrchestrationDagResponse(OrchestrationCamelModel):
    nodes: list[OrchestrationDagNodeResponse] = Field(default_factory=list)
    edges: list[OrchestrationDagEdgeResponse] = Field(default_factory=list)
    stats: OrchestrationDagStatsResponse


class OrchestrationRunResponse(OrchestrationCamelModel):
    """Full orchestration run record."""

    source: Literal["overnight-oats"] = "overnight-oats"
    contract_version: str
    run_id: str
    run_title: str
    repo_root: str
    config_path: str
    run_spec_path: str
    mode: str
    integration_branch: str
    task_pr_target: str
    final_pr_target: str
    status: OrchestrationRunStatus
    active_task_id: str | None = None
    heartbeat_at: str | None = None
    finished_at: str | None = None
    planner: OrchestrationInvocationResponse | None = None
    tasks: list[OrchestrationTaskResponse] = Field(default_factory=list)
    created_at: str
    last_updated_at: str
    is_running: bool = False
    recorded_at: str
    record_path: str
    dag: OrchestrationDagResponse
