from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class PrefectTaskRepoContext(BaseModel):
    integration_branch: str
    task_branch: str
    worktree_path: Path


class PrefectTaskNode(BaseModel):
    task_id: str
    title: str
    prompt: str
    depends_on: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    repo_context: PrefectTaskRepoContext | None = None


class PrefectTaskEdge(BaseModel):
    upstream_task_id: str
    downstream_task_id: str


class PrefectTaskGraph(BaseModel):
    nodes: list[PrefectTaskNode] = Field(default_factory=list)
    edges: list[PrefectTaskEdge] = Field(default_factory=list)


class PrefectFlowPayload(BaseModel):
    run_title: str
    source_path: Path
    repo_root: Path
    config_path: Path
    repo_base_branch: str
    worktree_dir: str
    default_concurrency: int
    default_validation_commands: list[str] = Field(default_factory=list)
    tasks: list[PrefectTaskNode] = Field(default_factory=list)
    task_graph: PrefectTaskGraph


class PrefectDeploymentSpec(BaseModel):
    flow_name: str
    deployment_name: str
    entrypoint: str
    description: str
    work_pool_name: str
    work_queue_name: str
    tags: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    task_graph: PrefectTaskGraph
    flow_payload: PrefectFlowPayload
