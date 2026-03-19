"""Application-layer shaping for legacy OATS local-runtime records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from pydantic import ConfigDict, InstanceOf, validate_call

from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.ports.orchestration import StoredOatsRunRecord, StoredOatsRuntimeState
from helaicopter_api.schema.orchestration import (
    OrchestrationDagEdgeResponse,
    OrchestrationDagNodeResponse,
    OrchestrationDagResponse,
    OrchestrationDagStatsResponse,
    OrchestrationInvocationResponse,
    OrchestrationRunResponse,
    OrchestrationTaskResponse,
)
from oats.models import (
    AgentInvocationResult,
    InvocationRuntimeRecord,
    RunExecutionRecord,
    TaskExecutionRecord,
    TaskRuntimeRecord,
)

ACTIVE_RUN_STATUSES = {"pending", "planning", "running"}


@dataclass(frozen=True, slots=True)
class _ShapedRun:
    response: OrchestrationRunResponse
    last_updated_at: datetime

    @property
    def is_running(self) -> bool:
        return self.response.is_running


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def list_oats_runs(services: InstanceOf[BackendServices]) -> list[OrchestrationRunResponse]:
    """Return legacy OATS local-runtime summaries for compatibility views."""
    runs_by_id: dict[str, _ShapedRun] = {}

    for stored_record in services.oats_run_store.list_run_records():
        shaped = _shape_run_record(stored_record)
        _merge_run(runs_by_id, shaped)

    for stored_state in services.oats_run_store.list_runtime_states():
        shaped = _shape_runtime_state(stored_state)
        _merge_run(runs_by_id, shaped)

    return [
        shaped.response
        for shaped in sorted(
            runs_by_id.values(),
            key=lambda item: (item.is_running, item.last_updated_at, item.response.run_id),
            reverse=True,
        )
    ]


def _merge_run(runs_by_id: dict[str, _ShapedRun], shaped: _ShapedRun) -> None:
    existing = runs_by_id.get(shaped.response.run_id)
    if existing is None:
        runs_by_id[shaped.response.run_id] = shaped
        return
    if shaped.is_running and not existing.is_running:
        runs_by_id[shaped.response.run_id] = shaped
        return
    if shaped.last_updated_at >= existing.last_updated_at:
        runs_by_id[shaped.response.run_id] = shaped


def _shape_runtime_state(stored: StoredOatsRuntimeState) -> _ShapedRun:
    state = stored.state
    repo_root = state.repo_root
    heartbeat_at = _isoformat(state.heartbeat_at)
    planner = _shape_invocation(state.planner, repo_root)
    tasks = [_shape_runtime_task(task, repo_root) for task in state.tasks]
    last_updated_at = _coerce_datetime(state.updated_at)
    response = OrchestrationRunResponse(
        source="overnight-oats",
        contract_version=state.contract_version,
        run_id=state.run_id,
        run_title=state.run_title,
        repo_root=str(repo_root),
        config_path=str(state.config_path),
        run_spec_path=str(state.run_spec_path),
        mode=state.mode,
        integration_branch=state.integration_branch,
        task_pr_target=state.task_pr_target,
        final_pr_target=state.final_pr_target,
        status=state.status,
        active_task_id=state.active_task_id,
        heartbeat_at=heartbeat_at,
        finished_at=_isoformat(state.finished_at),
        planner=planner,
        tasks=tasks,
        created_at=_isoformat(state.started_at) or heartbeat_at or "",
        last_updated_at=_isoformat(last_updated_at) or "",
        is_running=state.status in ACTIVE_RUN_STATUSES and state.finished_at is None,
        recorded_at=_isoformat(state.updated_at) or heartbeat_at or "",
        record_path=str(stored.path),
        dag=_build_orchestration_dag(
            planner,
            tasks,
            run_title=state.run_title,
            run_status=state.status,
            active_task_id=state.active_task_id,
            heartbeat_at=heartbeat_at,
        ),
    )
    return _ShapedRun(response=response, last_updated_at=last_updated_at)


def _shape_run_record(stored: StoredOatsRunRecord) -> _ShapedRun:
    record = stored.record
    repo_root = record.repo_root
    planner = _shape_invocation(record.planner, repo_root)
    tasks = [_shape_record_task(task, repo_root) for task in record.tasks]
    recorded_at = _coerce_datetime(record.recorded_at)
    status = _derive_run_status(record)
    response = OrchestrationRunResponse(
        source="overnight-oats",
        contract_version="oats-run-v1",
        run_id=record.run_id or stored.path.stem,
        run_title=record.run_title,
        repo_root=str(repo_root),
        config_path=str(record.config_path),
        run_spec_path=str(record.run_spec_path),
        mode=record.mode,
        integration_branch=record.integration_branch,
        task_pr_target=record.task_pr_target,
        final_pr_target=record.final_pr_target,
        status=status,
        active_task_id=None,
        heartbeat_at=_isoformat(recorded_at),
        finished_at=_isoformat(recorded_at),
        planner=planner,
        tasks=tasks,
        created_at=_isoformat(recorded_at) or "",
        last_updated_at=_isoformat(recorded_at) or "",
        is_running=False,
        recorded_at=_isoformat(recorded_at) or "",
        record_path=str(stored.path),
        dag=_build_orchestration_dag(
            planner,
            tasks,
            run_title=record.run_title,
            run_status=status,
            active_task_id=None,
            heartbeat_at=_isoformat(recorded_at),
        ),
    )
    return _ShapedRun(response=response, last_updated_at=recorded_at)


def _shape_runtime_task(task: TaskRuntimeRecord, repo_root: Path) -> OrchestrationTaskResponse:
    invocation = _shape_invocation(
        task.invocation,
        repo_root,
        fallback_agent=task.agent,
        fallback_role=task.role,
    )
    return OrchestrationTaskResponse(
        task_id=task.task_id,
        title=task.title,
        depends_on=list(task.depends_on),
        status=task.status,
        attempts=task.attempts,
        invocation=invocation,
    )


def _shape_record_task(task: TaskExecutionRecord, repo_root: Path) -> OrchestrationTaskResponse:
    invocation = _shape_invocation(task.invocation, repo_root)
    return OrchestrationTaskResponse(
        task_id=task.task_id,
        title=task.title,
        depends_on=list(task.depends_on),
        status=_derive_task_status(task.invocation),
        attempts=0,
        invocation=invocation,
    )


def _shape_invocation(
    invocation: AgentInvocationResult | InvocationRuntimeRecord | None,
    repo_root: Path,
    *,
    fallback_agent: str | None = None,
    fallback_role: str | None = None,
) -> OrchestrationInvocationResponse | None:
    if invocation is None:
        if fallback_agent is None or fallback_role is None:
            return None
        session_id = None
        agent = fallback_agent
        role = fallback_role
        command: list[str] = []
        cwd = str(repo_root)
        prompt = ""
        output_text = ""
        raw_stdout = ""
        raw_stderr = ""
        exit_code = None
        timed_out = False
        started_at = ""
        finished_at = None
    else:
        session_id = invocation.session_id
        agent = invocation.agent
        role = invocation.role
        command = list(invocation.command)
        cwd = str(invocation.cwd)
        prompt = invocation.prompt
        output_text = invocation.output_text
        raw_stdout = invocation.raw_stdout
        raw_stderr = invocation.raw_stderr
        exit_code = invocation.exit_code
        timed_out = invocation.timed_out
        started_at = _isoformat(invocation.started_at) or ""
        finished_at = _isoformat(invocation.finished_at)

    project_path = _normalize_repo_project_path(str(repo_root), agent) if session_id else None
    conversation_path = (
        f"/conversations/{quote(project_path, safe='')}/{session_id}"
        if project_path and session_id
        else None
    )
    return OrchestrationInvocationResponse(
        agent=agent,
        role=role,
        command=command,
        cwd=cwd,
        prompt=prompt,
        session_id=session_id,
        output_text=output_text,
        raw_stdout=raw_stdout,
        raw_stderr=raw_stderr,
        exit_code=exit_code,
        timed_out=timed_out,
        started_at=started_at,
        finished_at=finished_at,
        project_path=project_path,
        conversation_path=conversation_path,
    )


def _normalize_repo_project_path(repo_root: str, agent: str) -> str | None:
    encoded = repo_root.replace("/", "-")
    if agent == "codex":
        return f"codex:{encoded}"
    if agent == "claude":
        return encoded
    return None


def _derive_task_status(invocation: AgentInvocationResult) -> str:
    if invocation.timed_out:
        return "timed_out"
    if invocation.exit_code == 0:
        return "succeeded"
    return "failed"


def _derive_run_status(record: RunExecutionRecord) -> str:
    if record.planner is not None:
        if record.planner.timed_out:
            return "timed_out"
        if record.planner.exit_code != 0:
            return "failed"
    task_statuses = [_derive_task_status(task.invocation) for task in record.tasks]
    if "timed_out" in task_statuses:
        return "timed_out"
    if "failed" in task_statuses:
        return "failed"
    return "completed"


def _build_orchestration_dag(
    planner: OrchestrationInvocationResponse | None,
    tasks: list[OrchestrationTaskResponse],
    *,
    run_title: str,
    run_status: str,
    active_task_id: str | None,
    heartbeat_at: str | None,
) -> OrchestrationDagResponse:
    nodes: dict[str, OrchestrationDagNodeResponse] = {}
    edges: dict[str, OrchestrationDagEdgeResponse] = {}

    if planner is not None:
        nodes["planner"] = OrchestrationDagNodeResponse(
            id="planner",
            kind="planner",
            label="Planner",
            description=run_title,
            role=planner.role,
            agent=planner.agent,
            session_id=planner.session_id,
            project_path=planner.project_path,
            conversation_path=planner.conversation_path,
            status="running" if run_status == "planning" else run_status,
            is_active=run_status == "planning",
            last_heartbeat_at=heartbeat_at,
            exit_code=planner.exit_code,
            timed_out=planner.timed_out,
            depth=0,
        )

    for task in tasks:
        invocation = task.invocation
        nodes[task.task_id] = OrchestrationDagNodeResponse(
            id=task.task_id,
            kind="task",
            label=task.task_id,
            description=task.title,
            role=invocation.role if invocation is not None else "executor",
            agent=invocation.agent if invocation is not None else "executor",
            session_id=invocation.session_id if invocation is not None else None,
            project_path=invocation.project_path if invocation is not None else None,
            conversation_path=invocation.conversation_path if invocation is not None else None,
            status=task.status,
            is_active=active_task_id == task.task_id or task.status == "running",
            attempts=task.attempts,
            last_heartbeat_at=heartbeat_at,
            exit_code=invocation.exit_code if invocation is not None else None,
            timed_out=invocation.timed_out if invocation is not None else False,
            depth=1 if planner is not None else 0,
        )

    for task in tasks:
        if planner is not None and not task.depends_on:
            edge_id = f"planner->{task.task_id}"
            edges[edge_id] = OrchestrationDagEdgeResponse(
                id=edge_id,
                source="planner",
                target=task.task_id,
                label="dispatches",
            )
        for dependency in task.depends_on:
            edge_id = f"{dependency}->{task.task_id}"
            edges[edge_id] = OrchestrationDagEdgeResponse(
                id=edge_id,
                source=dependency,
                target=task.task_id,
                label="depends_on",
            )

    indegree = {node_id: 0 for node_id in nodes}
    children = {node_id: [] for node_id in nodes}
    for edge in edges.values():
        indegree[edge.target] = indegree.get(edge.target, 0) + 1
        children.setdefault(edge.source, []).append(edge.target)

    queue = [node_id for node_id, degree in indegree.items() if degree == 0]
    while queue:
        current_id = queue.pop(0)
        current = nodes.get(current_id)
        if current is None:
            continue
        for child_id in children.get(current_id, []):
            child = nodes.get(child_id)
            if child is None:
                continue
            if child.depth < current.depth + 1:
                child.depth = current.depth + 1
            indegree[child_id] = indegree.get(child_id, 0) - 1
            if indegree[child_id] == 0:
                queue.append(child_id)

    ordered_nodes = sorted(nodes.values(), key=lambda node: (node.depth, node.id))
    ordered_edges = sorted(edges.values(), key=lambda edge: edge.id)

    breadth_by_depth: dict[int, int] = {}
    provider_breakdown: dict[str, int] = {}
    for node in ordered_nodes:
        breadth_by_depth[node.depth] = breadth_by_depth.get(node.depth, 0) + 1
        provider_breakdown[node.agent] = provider_breakdown.get(node.agent, 0) + 1

    stats = OrchestrationDagStatsResponse(
        total_nodes=len(ordered_nodes),
        total_edges=len(ordered_edges),
        max_depth=max((node.depth for node in ordered_nodes), default=0),
        max_breadth=max(breadth_by_depth.values(), default=0),
        root_count=sum(
            1
            for node in ordered_nodes
            if not any(edge.target == node.id for edge in ordered_edges)
        ),
        provider_breakdown=provider_breakdown,
        timed_out_count=sum(1 for node in ordered_nodes if node.timed_out),
        active_count=sum(1 for node in ordered_nodes if node.is_active),
        pending_count=sum(1 for node in ordered_nodes if node.status == "pending"),
        failed_count=sum(1 for node in ordered_nodes if node.status == "failed"),
        succeeded_count=sum(1 for node in ordered_nodes if node.status == "succeeded"),
    )
    return OrchestrationDagResponse(nodes=ordered_nodes, edges=ordered_edges, stats=stats)


def _coerce_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _coerce_datetime(value).isoformat().replace("+00:00", "Z")
