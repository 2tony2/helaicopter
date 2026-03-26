"""Schemas for live runtime materialization."""

from __future__ import annotations

from helaicopter_api.schema.common import CamelCaseHttpResponseModel


class MaterializedTaskAttempt(CamelCaseHttpResponseModel):
    task_id: str
    attempt_id: str | None = None
    worker_id: str | None = None
    provider_session_id: str | None = None
    session_reused: bool = False
    session_status_after_task: str | None = None
    status: str
    duration_seconds: float | None = None
    branch_name: str | None = None
    commit_sha: str | None = None
    error_summary: str | None = None


class MaterializedGraphMutation(CamelCaseHttpResponseModel):
    mutation_id: str
    kind: str
    discovered_by: str
    source: str
    timestamp: str | None = None
    nodes_added: list[str] = []


class MaterializedDispatchEvent(CamelCaseHttpResponseModel):
    run_id: str
    task_id: str
    worker_id: str
    provider: str
    model: str
    dispatched_at: str


class MaterializedOperatorAction(CamelCaseHttpResponseModel):
    action: str
    actor: str
    created_at: str
    target_task_id: str | None = None
    details: dict[str, object] = {}


class MaterializedRuntimeRun(CamelCaseHttpResponseModel):
    run_id: str
    source: str
    task_attempts: list[MaterializedTaskAttempt]
    graph_mutations: list[MaterializedGraphMutation]
    dispatch_events: list[MaterializedDispatchEvent]
    operator_actions: list[MaterializedOperatorAction] = []
