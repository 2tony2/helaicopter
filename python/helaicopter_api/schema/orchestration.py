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
    last_heartbeat_at: str | None = None
    finished_at: str | None = None
    project_path: EncodedProjectKey | None = None
    conversation_path: str | None = None


class OrchestrationTaskResponse(CamelCaseHttpResponseModel):
    """A single task within an orchestration run."""

    task_id: TaskId
    title: str
    depends_on: list[str] = []
    parent_branch: str | None = None
    status: TaskRuntimeStatus
    attempts: int = 0
    task_pr: "OrchestrationTaskPullRequestResponse | None" = None
    operation_history: list["OrchestrationOperationHistoryResponse"] = []
    invocation: OrchestrationInvocationResponse | None = None


class OrchestrationFeatureBranchResponse(CamelCaseHttpResponseModel):
    """Feature branch associated with an orchestration run."""

    name: str
    base_branch: str | None = None


class OrchestrationReviewSummaryResponse(CamelCaseHttpResponseModel):
    """Aggregated pull request review state for an orchestration task."""

    blocking_state: str
    approvals: int = 0
    changes_requested: int = 0


class OrchestrationTaskPullRequestResponse(CamelCaseHttpResponseModel):
    """Pull request snapshot for an individual orchestration task branch."""

    number: int | None = None
    url: str | None = None
    state: str
    merge_gate_status: str
    base_branch: str | None = None
    head_branch: str | None = None
    mergeability: str | None = None
    checks_summary: dict[str, object] = {}
    review_summary: OrchestrationReviewSummaryResponse | None = None
    snapshot_source: str | None = None
    last_refreshed_at: str | None = None
    is_stale: bool = False


class OrchestrationFinalPullRequestResponse(CamelCaseHttpResponseModel):
    """Final integration pull request snapshot for a completed orchestration run."""

    number: int | None = None
    url: str | None = None
    state: str
    review_gate_status: str
    base_branch: str | None = None
    head_branch: str | None = None
    checks_summary: dict[str, object] = {}
    snapshot_source: str | None = None
    last_refreshed_at: str | None = None
    is_stale: bool = False


class OrchestrationOperationHistoryResponse(CamelCaseHttpResponseModel):
    """A single recorded operation event in an orchestration run or task history."""

    kind: str
    status: str
    session_id: SessionId | None = None
    started_at: str
    finished_at: str | None = None
    details: dict[str, object] = {}


class OrchestrationDagNodeResponse(CamelCaseHttpResponseModel):
    """A single node (planner or task) in the orchestration run DAG."""

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
    """A directed dependency edge between two nodes in the orchestration DAG."""

    id: str
    source: str
    target: str
    label: str | None = None


class OrchestrationDagStatsResponse(CamelCaseHttpResponseModel):
    """Aggregate structural and status statistics for an orchestration run DAG."""

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
    """Complete DAG representation for an orchestration run, including nodes, edges, and stats."""

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
    stack_status: str | None = None
    feature_branch: OrchestrationFeatureBranchResponse | None = None
    active_task_id: TaskId | None = None
    heartbeat_at: str | None = None
    finished_at: str | None = None
    planner: OrchestrationInvocationResponse | None = None
    tasks: list[OrchestrationTaskResponse] = []
    final_pr: OrchestrationFinalPullRequestResponse | None = None
    operation_history: list[OrchestrationOperationHistoryResponse] = []
    created_at: str
    last_updated_at: str
    is_running: bool = False
    recorded_at: str
    record_path: str
    dag: OrchestrationDagResponse


class OrchestrationRunFactResponse(CamelCaseHttpResponseModel):
    """Canonical fact record summarising the outcome of a single orchestration run."""

    run_id: RunId
    run_title: str
    source_kind: Literal["runtime_snapshot", "terminal_record"]
    canonical_reason: str
    status: RunRuntimeStatus
    task_count: int = 0
    attempt_count: int = 0
    completed_task_count: int = 0
    failed_task_count: int = 0
    pending_task_count: int = 0
    running_task_count: int = 0
    timed_out_task_count: int = 0
    active_task_id: TaskId | None = None
    is_running: bool = False
    is_stale: bool = False
    runtime_state_path: str | None = None
    terminal_record_path: str | None = None


class OrchestrationTaskAttemptFactResponse(CamelCaseHttpResponseModel):
    """Canonical fact record for a single task attempt within an orchestration run."""

    run_id: RunId
    task_id: TaskId
    task_title: str
    attempt_number: int
    source_kind: Literal["runtime_snapshot", "terminal_record"]
    status: TaskRuntimeStatus
    agent: ProviderName | None = None
    session_id: SessionId | None = None
    exit_code: int | None = None
    timed_out: bool = False


class OrchestrationFactsResponse(CamelCaseHttpResponseModel):
    """Canonical routing facts for all runs and task attempts across a project."""

    canonical_rules: list[str] = []
    run_facts: list[OrchestrationRunFactResponse] = []
    task_attempt_facts: list[OrchestrationTaskAttemptFactResponse] = []
