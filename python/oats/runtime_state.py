from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import uuid

from oats.models import (
    AgentInvocationResult,
    ExecutionPlan,
    InvocationRuntimeRecord,
    RunPlanSnapshot,
    RunRuntimeState,
    RuntimeProgressEvent,
    TaskRuntimeRecord,
)


def build_run_id(run_spec_path: Path) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", run_spec_path.stem.lower()).strip("-")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stem or 'run'}-{timestamp}"


def build_initial_runtime_state(
    execution_plan: ExecutionPlan,
    *,
    mode: str,
    run_id: str,
    executor_agent: str,
) -> RunRuntimeState:
    runtime_dir = execution_plan.repo_root / ".oats" / "runtime" / run_id
    tasks = [
        TaskRuntimeRecord(
            task_id=task.id,
            title=task.title,
            depends_on=task.depends_on,
            branch_name=task.branch_name,
            pr_base=task.pr_base,
            agent=executor_agent,
        )
        for task in execution_plan.tasks
    ]
    now = datetime.now(timezone.utc)
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
        status="pending",
        started_at=now,
        updated_at=now,
        heartbeat_at=now,
        tasks=tasks,
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
) -> Path:
    state.runtime_dir.mkdir(parents=True, exist_ok=True)
    path = state.runtime_dir / "events.jsonl"
    event = RuntimeProgressEvent(
        run_id=state.run_id,
        event_type=event_type,
        run_status=state.status,
        task_id=task_id,
        message=message,
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
    status: str,
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
    agent: str,
    role: str,
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
        invocation.session_id = session_id
    if session_id_field:
        invocation.session_id_field = session_id_field
    if requested_session_id:
        invocation.requested_session_id = requested_session_id
    if output_text:
        invocation.output_text = output_text
    invocation.last_heartbeat_at = datetime.now(timezone.utc)


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


def _atomic_write_text(path: Path, content: str) -> None:
    temp_path = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)
