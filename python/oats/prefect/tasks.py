from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
import uuid

from prefect import task
from prefect.runtime import flow_run, task_run
from pydantic import BaseModel, Field

from oats.models import PlannedTask
from oats.prefect.artifacts import LocalArtifactCheckpointStore
from oats.prefect.models import PrefectFlowPayload, PrefectTaskNode
from oats.prefect.worktree import prepare_task_worktree
from oats.repo_config import load_repo_config
from oats.runner import AgentInvocationError, build_task_prompt, invoke_agent


_PREFECT_TASK_STALE_AFTER_SECONDS = 300.0


class TaskExecutor(Protocol):
    def __call__(
        self,
        payload: PrefectFlowPayload,
        task_node: PrefectTaskNode,
        upstream_results: dict[str, dict[str, object]],
        attempt: int,
        worktree_path: Path,
    ) -> dict[str, object]: ...


class CompiledTaskResult(BaseModel):
    task_id: str
    attempt: int
    status: str
    upstream_task_ids: list[str] = Field(default_factory=list)
    result: dict[str, object] = Field(default_factory=dict)


@dataclass
class _LiveCheckpointState:
    session_id: str | None = None
    session_id_field: str | None = None
    requested_session_id: str | None = None
    output_text: str | None = None
    last_heartbeat_at: str | None = None
    last_progress_event_at: str | None = None


def run_task_with_retries(
    payload: PrefectFlowPayload,
    task_node: PrefectTaskNode,
    *,
    upstream_results: dict[str, dict[str, object]],
    artifact_store: LocalArtifactCheckpointStore,
    max_retries: int,
    executor: Any = None,
) -> CompiledTaskResult:
    attempt = 1
    while True:
        try:
            return execute_compiled_task_attempt(
                payload,
                task_node,
                upstream_results=upstream_results,
                artifact_store=artifact_store,
                executor=executor,
                attempt=attempt,
            )
        except Exception:
            if attempt > max_retries:
                raise
            attempt += 1


def execute_compiled_task_attempt(
    payload: PrefectFlowPayload,
    task_node: PrefectTaskNode,
    *,
    upstream_results: dict[str, dict[str, object]],
    artifact_store: LocalArtifactCheckpointStore,
    executor: Any = None,
    attempt: int | None = None,
) -> CompiledTaskResult:
    resolved_attempt = attempt if attempt is not None else _resolve_attempt()
    if _task_is_merge_gated(task_node) and not _upstream_prs_merged(task_node, artifact_store):
        artifact_store.write_task_checkpoint(
            task_node,
            status="blocked",
            attempt=resolved_attempt,
            upstream_task_ids=list(upstream_results),
            merge_gate_status="not_ready",
        )
        return CompiledTaskResult(
            task_id=task_node.task_id,
            attempt=resolved_attempt,
            status="blocked",
            upstream_task_ids=sorted(upstream_results),
        )
    prepared_worktree = prepare_task_worktree(payload, task_node)
    live_state = _LiveCheckpointState()
    artifact_store.write_task_checkpoint(
        task_node,
        status="running",
        attempt=resolved_attempt,
        upstream_task_ids=list(upstream_results),
    )

    try:
        if executor is None:
            task_result = _oats_executor(
                payload,
                task_node,
                upstream_results,
                resolved_attempt,
                prepared_worktree.worktree_path,
                artifact_store=artifact_store,
                live_state=live_state,
            )
        else:
            task_result = executor(
                payload,
                task_node,
                upstream_results,
                resolved_attempt,
                prepared_worktree.worktree_path,
            )
    except Exception as exc:
        artifact_store.write_task_checkpoint(
            task_node,
            status="failed",
            attempt=resolved_attempt,
            upstream_task_ids=list(upstream_results),
            session_id=live_state.session_id,
            session_id_field=live_state.session_id_field,
            requested_session_id=live_state.requested_session_id,
            output_text=live_state.output_text,
            last_heartbeat_at=live_state.last_heartbeat_at,
            last_progress_event_at=live_state.last_progress_event_at,
            error=str(exc),
        )
        raise

    result = CompiledTaskResult(
        task_id=task_node.task_id,
        attempt=resolved_attempt,
        status="completed",
        upstream_task_ids=sorted(upstream_results),
        result=dict(task_result),
    )
    artifact_store.write_task_checkpoint(
        task_node,
        status=result.status,
        attempt=result.attempt,
        upstream_task_ids=result.upstream_task_ids,
        session_id=live_state.session_id,
        session_id_field=live_state.session_id_field,
        requested_session_id=live_state.requested_session_id,
        output_text=live_state.output_text,
        last_heartbeat_at=live_state.last_heartbeat_at,
        last_progress_event_at=live_state.last_progress_event_at,
        result=result.result,
    )
    return result


prefect_compiled_task = task(name="oats-compiled-task", retries=2, retry_delay_seconds=0)(
    execute_compiled_task_attempt
)


def resolve_flow_run_identity(
    *,
    flow_run_id: str | None = None,
    flow_run_name: str | None = None,
) -> tuple[str, str | None]:
    resolved_id = flow_run_id or _runtime_value(lambda: flow_run.id) or f"local-{uuid.uuid4().hex}"
    resolved_name = flow_run_name or _runtime_value(lambda: flow_run.name)
    return resolved_id, resolved_name


def _default_executor(
    payload: PrefectFlowPayload,
    task_node: PrefectTaskNode,
    upstream_results: dict[str, dict[str, object]],
    attempt: int,
    worktree_path: Path,
    *,
    artifact_store: LocalArtifactCheckpointStore | None = None,
    live_state: _LiveCheckpointState | None = None,
) -> dict[str, object]:
    del payload, worktree_path, artifact_store, live_state
    return {
        "task_id": task_node.task_id,
        "title": task_node.title,
        "attempt": attempt,
        "upstream_task_ids": sorted(upstream_results),
    }


def _oats_executor(
    payload: PrefectFlowPayload,
    task_node: PrefectTaskNode,
    upstream_results: dict[str, dict[str, object]],
    attempt: int,
    worktree_path: Path,
    *,
    artifact_store: LocalArtifactCheckpointStore | None = None,
    live_state: _LiveCheckpointState | None = None,
) -> dict[str, object]:
    config = load_repo_config(payload.config_path)
    planned_task = PlannedTask(
        id=task_node.task_id,
        title=task_node.title,
        prompt=task_node.prompt,
        depends_on=list(task_node.depends_on),
        agent=task_node.agent,
        model=task_node.model,
        reasoning_effort=task_node.reasoning_effort,
        acceptance_criteria=list(task_node.acceptance_criteria),
        validation_commands=list(task_node.validation_commands),
        branch_name=(task_node.repo_context.task_branch if task_node.repo_context else task_node.task_id),
        parent_branch=(
            task_node.repo_context.parent_branch
            if task_node.repo_context
            else payload.repo_base_branch
        ),
        pr_base=(
            task_node.repo_context.pr_base
            if task_node.repo_context
            else payload.repo_base_branch
        ),
        branch_strategy=task_node.branch_strategy,
        initial_task_status=task_node.initial_task_status,
    )
    prompt = build_task_prompt(
        planned_task,
        payload.run_title,
        read_only=False,
    )
    dangerous_bypass = getattr(getattr(config, "execution", None), "dangerous_bypass", False)
    result = invoke_agent(
        agent_name=planned_task.agent,
        agent_command=config.agent[planned_task.agent],
        role="executor",
        cwd=worktree_path,
        prompt=prompt,
        read_only=False,
        timeout_seconds=1800,
        dangerous_bypass=dangerous_bypass,
        model=planned_task.model,
        reasoning_effort=planned_task.reasoning_effort,
        raise_on_nonzero=False,
        stale_after_seconds=_PREFECT_TASK_STALE_AFTER_SECONDS,
        on_heartbeat=(
            lambda: _record_prefect_heartbeat(
                artifact_store,
                task_node,
                attempt=attempt,
                upstream_task_ids=sorted(upstream_results),
                live_state=live_state,
            )
        ),
        on_progress=(
            lambda progress: _record_prefect_progress(
                artifact_store,
                task_node,
                attempt=attempt,
                upstream_task_ids=sorted(upstream_results),
                live_state=live_state,
                progress=progress,
            )
        ),
    )
    _apply_agent_result_to_live_state(live_state, result)
    if result.timed_out:
        raise TimeoutError(
            f"Executor timed out for task {task_node.task_id} on attempt {attempt}"
        )
    if result.exit_code != 0:
        raise AgentInvocationError(
            f"Executor failed for task {task_node.task_id} with exit code {result.exit_code}\n"
            f"stderr:\n{result.raw_stderr or '<empty>'}"
        )
    return {
        "task_id": task_node.task_id,
        "title": task_node.title,
        "attempt": attempt,
        "upstream_task_ids": sorted(upstream_results),
        "agent": result.agent,
        "model": planned_task.model,
        "reasoning_effort": planned_task.reasoning_effort,
        "session_id": str(result.session_id) if result.session_id is not None else None,
        "output_text": result.output_text,
    }


def _resolve_attempt() -> int:
    value = _runtime_value(task_run.run_count)
    if isinstance(value, int) and value >= 1:
        return value
    return 1


def _task_is_merge_gated(task_node: PrefectTaskNode) -> bool:
    return (
        task_node.initial_task_status == "blocked"
        or task_node.branch_strategy == "after_dependency_merges"
    )


def _upstream_prs_merged(
    task_node: PrefectTaskNode,
    artifact_store: LocalArtifactCheckpointStore,
) -> bool:
    for dependency in task_node.depends_on:
        checkpoint = artifact_store.read_task_checkpoint(dependency)
        if checkpoint is None:
            return False
        task_pr = checkpoint.task_pr or {}
        if task_pr.get("state") != "merged":
            return False
    return True


def _runtime_value(getter: Callable[[], Any] | Any) -> Any:
    try:
        return getter() if callable(getter) else getter
    except Exception:
        return None


def _record_prefect_heartbeat(
    artifact_store: LocalArtifactCheckpointStore | None,
    task_node: PrefectTaskNode,
    *,
    attempt: int,
    upstream_task_ids: list[str],
    live_state: _LiveCheckpointState | None,
) -> None:
    if artifact_store is None or live_state is None:
        return
    live_state.last_heartbeat_at = _utc_now()
    artifact_store.write_task_checkpoint(
        task_node,
        status="running",
        attempt=attempt,
        upstream_task_ids=upstream_task_ids,
        session_id=live_state.session_id,
        session_id_field=live_state.session_id_field,
        requested_session_id=live_state.requested_session_id,
        output_text=live_state.output_text,
        last_heartbeat_at=live_state.last_heartbeat_at,
        last_progress_event_at=live_state.last_progress_event_at,
    )


def _record_prefect_progress(
    artifact_store: LocalArtifactCheckpointStore | None,
    task_node: PrefectTaskNode,
    *,
    attempt: int,
    upstream_task_ids: list[str],
    live_state: _LiveCheckpointState | None,
    progress: dict[str, str],
) -> None:
    if artifact_store is None or live_state is None:
        return
    if progress.get("session_id"):
        live_state.session_id = progress["session_id"]
    if progress.get("session_id_field"):
        live_state.session_id_field = progress["session_id_field"]
    if progress.get("requested_session_id"):
        live_state.requested_session_id = progress["requested_session_id"]
    if progress.get("output_text"):
        live_state.output_text = progress["output_text"]
        live_state.last_progress_event_at = _utc_now()
    live_state.last_heartbeat_at = _utc_now()
    artifact_store.write_task_checkpoint(
        task_node,
        status="running",
        attempt=attempt,
        upstream_task_ids=upstream_task_ids,
        session_id=live_state.session_id,
        session_id_field=live_state.session_id_field,
        requested_session_id=live_state.requested_session_id,
        output_text=live_state.output_text,
        last_heartbeat_at=live_state.last_heartbeat_at,
        last_progress_event_at=live_state.last_progress_event_at,
    )


def _apply_agent_result_to_live_state(
    live_state: _LiveCheckpointState | None,
    result: Any,
) -> None:
    if live_state is None:
        return
    session_id = getattr(result, "session_id", None)
    if session_id is not None:
        live_state.session_id = str(session_id)
    session_id_field = getattr(result, "session_id_field", None)
    if session_id_field is not None:
        live_state.session_id_field = session_id_field
    requested_session_id = getattr(result, "requested_session_id", None)
    if requested_session_id is not None:
        live_state.requested_session_id = str(requested_session_id)
    output_text = getattr(result, "output_text", None)
    if output_text:
        live_state.output_text = output_text
        live_state.last_progress_event_at = _utc_now()
    if live_state.last_heartbeat_at is None:
        live_state.last_heartbeat_at = _utc_now()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
