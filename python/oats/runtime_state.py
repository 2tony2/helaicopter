from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Literal, cast
import uuid

from helaicopter_domain.ids import RunId, SessionId, TaskId
from helaicopter_domain.vocab import ProviderName, RunRuntimeStatus
from oats.graph import EdgePredicate, TaskGraph, TaskKind, TaskNode, TypedEdge
from oats.models import (
    AgentInvocationResult,
    ExecutionPlan,
    FeatureBranchSnapshot,
    InvocationRuntimeRecord,
    PlannedTask,
    RunPlanSnapshot,
    RunRuntimeState,
    RuntimeProgressEvent,
    TaskPullRequestSnapshot,
    TaskRuntimeRecord,
)


def build_run_id(run_spec_path: Path) -> RunId:
    stem = re.sub(r"[^a-z0-9]+", "-", run_spec_path.stem.lower()).strip("-")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return RunId(f"{stem or 'run'}-{timestamp}")


def build_initial_runtime_state(
    execution_plan: ExecutionPlan,
    *,
    mode: Literal["read-only", "writable"],
    run_id: RunId,
    executor_agent: ProviderName,
) -> RunRuntimeState:
    runtime_dir = execution_plan.repo_root / ".oats" / "runtime" / run_id
    tasks = [
        TaskRuntimeRecord(
            task_id=TaskId(task.id),
            title=task.title,
            depends_on=task.depends_on,
            branch_name=task.branch_name,
            parent_branch=task.parent_branch,
            pr_base=task.pr_base,
            agent=executor_agent,
            status=task.initial_task_status,
            task_pr=TaskPullRequestSnapshot(
                base_branch=task.pr_base,
                head_branch=task.branch_name,
            ),
        )
        for task in execution_plan.tasks
    ]
    now = datetime.now(timezone.utc)
    graph = build_graph_from_planned_tasks(execution_plan.tasks)
    return RunRuntimeState(
        run_id=run_id,
        run_title=execution_plan.run_title,
        repo_root=execution_plan.repo_root,
        config_path=execution_plan.config_path,
        run_spec_path=execution_plan.run_spec_path,
        mode=mode,
        integration_branch=execution_plan.integration_branch,
        task_pr_target=execution_plan.task_pr_target,
        final_pr_target=execution_plan.final_pr_target,
        runtime_dir=runtime_dir,
        feature_branch=FeatureBranchSnapshot(
            name=execution_plan.integration_branch,
            base_branch=execution_plan.integration_branch_base,
        ),
        status="pending",
        started_at=now,
        updated_at=now,
        heartbeat_at=now,
        tasks=tasks,
        graph=graph,
    )


def build_plan_snapshot(state: RunRuntimeState, execution_plan: ExecutionPlan) -> RunPlanSnapshot:
    return RunPlanSnapshot(
        run_id=state.run_id,
        run_title=state.run_title,
        repo_root=state.repo_root,
        config_path=state.config_path,
        run_spec_path=state.run_spec_path,
        mode=state.mode,
        integration_branch=state.integration_branch,
        task_pr_target=state.task_pr_target,
        final_pr_target=state.final_pr_target,
        tasks=execution_plan.tasks,
    )


def build_graph_from_planned_tasks(tasks: list[PlannedTask]) -> TaskGraph:
    """Build a TaskGraph from planned tasks.

    Single-parent deps get code_ready edges.
    Multi-dependency tasks with after_dependency_merges get pr_merged edges.
    """
    graph = TaskGraph()
    for task in tasks:
        graph.add_node(TaskNode(
            task_id=task.id,
            kind=TaskKind.IMPLEMENTATION,
            title=task.title,
        ))

    for task in tasks:
        if not task.depends_on:
            continue
        predicate = (
            EdgePredicate.PR_MERGED
            if task.branch_strategy == "after_dependency_merges"
            else EdgePredicate.CODE_READY
        )
        for dep_id in task.depends_on:
            graph.add_edge(TypedEdge(
                from_task=dep_id,
                to_task=task.id,
                predicate=predicate,
            ))
    return graph


def migrate_v1_state(state: RunRuntimeState) -> RunRuntimeState:
    """Auto-migrate a v1 state without a graph field.

    Creates the graph from the tasks array with code_ready edges
    (since v1 didn't have edge type information).
    """
    if state.graph is not None:
        return state

    graph = TaskGraph()
    for task in state.tasks:
        graph.add_node(TaskNode(
            task_id=task.task_id,
            kind=task.kind,
            title=task.title,
        ))
    for task in state.tasks:
        for dep_id in task.depends_on:
            if dep_id in graph.nodes:
                graph.add_edge(TypedEdge(
                    from_task=dep_id,
                    to_task=task.task_id,
                    predicate=EdgePredicate.CODE_READY,
                ))
    state.graph = graph
    return state


def load_runtime_state(path: Path) -> RunRuntimeState:
    return RunRuntimeState.model_validate_json(path.read_text())


def resolve_runtime_state(
    repo_root: Path,
    *,
    run_id: str | None = None,
    state_path: Path | None = None,
) -> RunRuntimeState:
    if state_path is not None:
        return load_runtime_state(state_path.resolve())

    runtime_root = repo_root / ".oats" / "runtime"
    if run_id:
        return load_runtime_state(runtime_root / run_id / "state.json")

    candidates = sorted(
        runtime_root.glob("*/state.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"No runtime state found under {runtime_root}")
    return load_runtime_state(candidates[0])


def write_plan_snapshot(snapshot: RunPlanSnapshot, runtime_dir: Path) -> Path:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    path = runtime_dir / "plan.json"
    _atomic_write_text(path, snapshot.model_dump_json(indent=2))
    return path


def write_runtime_state(state: RunRuntimeState) -> Path:
    state.runtime_dir.mkdir(parents=True, exist_ok=True)
    state.updated_at = datetime.now(timezone.utc)
    path = state.runtime_dir / "state.json"
    _atomic_write_text(path, state.model_dump_json(indent=2))
    return path


def append_progress_event(
    state: RunRuntimeState,
    *,
    event_type: str,
    task_id: str | None = None,
    message: str | None = None,
    agent: str | None = None,
    session_id: str | None = None,
    heartbeat_at: datetime | None = None,
    output_text: str | None = None,
) -> Path:
    state.runtime_dir.mkdir(parents=True, exist_ok=True)
    path = state.runtime_dir / "events.jsonl"
    event = RuntimeProgressEvent(
        run_id=state.run_id,
        event_type=event_type,
        run_status=state.status,
        task_id=TaskId(task_id) if task_id is not None else None,
        message=message,
        agent=cast("ProviderName | None", agent),
        session_id=SessionId(session_id) if session_id is not None else None,
        heartbeat_at=heartbeat_at,
        output_text=output_text,
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(event.model_dump_json())
        handle.write("\n")
    return path


def mark_run_started(state: RunRuntimeState) -> None:
    now = datetime.now(timezone.utc)
    state.status = "planning"
    state.started_at = now
    state.updated_at = now
    state.heartbeat_at = now


def mark_run_resumed(state: RunRuntimeState) -> None:
    now = datetime.now(timezone.utc)
    state.status = "planning"
    state.active_task_id = None
    state.updated_at = now
    state.heartbeat_at = now
    state.finished_at = None
    state.final_record_path = None


def mark_run_finished(
    state: RunRuntimeState,
    *,
    status: RunRuntimeStatus,
    final_record_path: Path | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    state.status = status
    state.active_task_id = None
    state.updated_at = now
    state.heartbeat_at = now
    state.finished_at = now
    state.final_record_path = final_record_path


def prepare_invocation_runtime(
    *,
    agent: ProviderName,
    role: Literal["planner", "executor", "conflict_resolver", "merge_operator"],
    cwd: Path,
    prompt: str,
) -> InvocationRuntimeRecord:
    now = datetime.now(timezone.utc)
    return InvocationRuntimeRecord(
        agent=agent,
        role=role,
        cwd=cwd,
        prompt=prompt,
        started_at=now,
        last_heartbeat_at=now,
    )


def refresh_invocation_heartbeat(invocation: InvocationRuntimeRecord | None) -> None:
    if invocation is None:
        return
    invocation.last_heartbeat_at = datetime.now(timezone.utc)


def update_invocation_progress(
    invocation: InvocationRuntimeRecord | None,
    *,
    session_id: str | None = None,
    session_id_field: str | None = None,
    requested_session_id: str | None = None,
    output_text: str | None = None,
) -> None:
    if invocation is None:
        return
    if session_id:
        invocation.session_id = SessionId(session_id)
    if session_id_field:
        invocation.session_id_field = session_id_field
    if requested_session_id:
        invocation.requested_session_id = SessionId(requested_session_id)
    if output_text:
        invocation.output_text = output_text
    invocation.last_heartbeat_at = datetime.now(timezone.utc)


def record_invocation_progress(
    state: RunRuntimeState,
    invocation: InvocationRuntimeRecord | None,
    *,
    event_type: str,
    task_id: str | None = None,
    session_id: str | None = None,
    session_id_field: str | None = None,
    requested_session_id: str | None = None,
    output_text: str | None = None,
) -> bool:
    if invocation is None:
        return False

    previous_output = invocation.output_text
    update_invocation_progress(
        invocation,
        session_id=session_id,
        session_id_field=session_id_field,
        requested_session_id=requested_session_id,
        output_text=output_text,
    )
    state.heartbeat_at = invocation.last_heartbeat_at or datetime.now(timezone.utc)

    normalized_output = (output_text or "").strip()
    changed = bool(normalized_output and normalized_output != previous_output.strip())
    if changed:
        append_progress_event(
            state,
            event_type=event_type,
            task_id=task_id,
            message=_summarize_output_text(normalized_output),
            agent=invocation.agent,
            session_id=invocation.session_id,
            heartbeat_at=invocation.last_heartbeat_at,
            output_text=normalized_output,
        )
        invocation.last_progress_event_at = invocation.last_heartbeat_at

    write_runtime_state(state)
    return changed


def record_invocation_heartbeat(
    state: RunRuntimeState,
    invocation: InvocationRuntimeRecord | None,
    *,
    event_type: str,
    task_id: str | None = None,
    min_interval_seconds: float = 30.0,
) -> bool:
    if invocation is None:
        return False

    refresh_invocation_heartbeat(invocation)
    state.heartbeat_at = invocation.last_heartbeat_at or datetime.now(timezone.utc)
    last_event_at = invocation.last_progress_event_at or invocation.started_at
    should_emit = (
        last_event_at is None
        or invocation.last_heartbeat_at is None
        or (invocation.last_heartbeat_at - last_event_at).total_seconds() >= min_interval_seconds
    )
    if should_emit:
        append_progress_event(
            state,
            event_type=event_type,
            task_id=task_id,
            message="heartbeat",
            agent=invocation.agent,
            session_id=invocation.session_id,
            heartbeat_at=invocation.last_heartbeat_at,
            output_text=invocation.output_text or None,
        )
        invocation.last_progress_event_at = invocation.last_heartbeat_at

    write_runtime_state(state)
    return should_emit


def apply_agent_result(
    invocation: InvocationRuntimeRecord,
    result: AgentInvocationResult,
) -> InvocationRuntimeRecord:
    invocation.command = result.command
    invocation.session_id = result.session_id
    invocation.session_id_field = result.session_id_field
    invocation.requested_session_id = result.requested_session_id
    invocation.output_text = result.output_text
    invocation.raw_stdout = result.raw_stdout
    invocation.raw_stderr = result.raw_stderr
    invocation.exit_code = result.exit_code
    invocation.timed_out = result.timed_out
    invocation.started_at = result.started_at
    invocation.last_heartbeat_at = result.finished_at
    invocation.finished_at = result.finished_at
    return invocation


def _summarize_output_text(output_text: str, *, limit: int = 240) -> str:
    compact = " ".join(output_text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3].rstrip()}..."


def _atomic_write_text(path: Path, content: str) -> None:
    temp_path = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)
