from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import json

from helaicopter_domain.vocab import RunRuntimeStatus, TaskRuntimeStatus
from oats.models import (
    AgentInvocationResult,
    InvocationRuntimeRecord,
    RunExecutionRecord,
    RunRuntimeState,
    TaskExecutionRecord,
    TaskRuntimeRecord,
)

from helaicopter_api.adapters.oats_artifacts import FileOatsRunStore

ACTIVE_RUN_STATUSES = {"pending", "planning", "running"}
STALE_RUNTIME_AFTER_SECONDS = 300


@dataclass(frozen=True, slots=True)
class OrchestrationRunFact:
    run_fact_id: str
    run_source: str
    run_id: str
    flow_run_name: str | None
    run_title: str
    source_path: str | None
    repo_root: str
    config_path: str | None
    artifact_root: str | None
    status: str
    canonical_status_source: str
    has_runtime_snapshot: bool
    has_terminal_record: bool
    task_count: int
    completed_task_count: int
    running_task_count: int
    failed_task_count: int
    task_attempt_count: int
    started_at: datetime | None
    updated_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class OrchestrationTaskAttemptFact:
    task_attempt_fact_id: str
    run_fact_id: str
    run_source: str
    run_id: str
    task_id: str
    task_title: str
    attempt: int
    status: str
    upstream_task_ids_json: str | None
    agent: str | None
    session_id: str | None
    model: str | None
    reasoning_effort: str | None
    error: str | None
    output_text: str | None
    started_at: datetime | None
    updated_at: datetime
    finished_at: datetime | None
    last_heartbeat_at: datetime | None
    last_progress_event_at: datetime | None


def collect_orchestration_facts(project_root: Path) -> tuple[list[OrchestrationRunFact], list[OrchestrationTaskAttemptFact]]:
    legacy_store = FileOatsRunStore(project_root=project_root, runtime_dir=project_root / ".oats" / "runtime")
    runtime_states = {str(item.state.run_id): item.state for item in legacy_store.list_runtime_states()}
    run_records = {
        str(item.record.run_id or item.path.stem): item.record
        for item in legacy_store.list_run_records()
    }

    run_facts: list[OrchestrationRunFact] = []
    task_attempt_facts: list[OrchestrationTaskAttemptFact] = []

    for run_id in sorted(set(runtime_states) | set(run_records)):
        runtime_state = runtime_states.get(run_id)
        run_record = run_records.get(run_id)
        run_fact = _build_legacy_run_fact(run_id, runtime_state=runtime_state, run_record=run_record)
        if run_fact is None:
            continue
        run_facts.append(run_fact)
        task_attempt_facts.extend(
            _build_legacy_task_attempt_facts(run_fact, runtime_state=runtime_state, run_record=run_record)
        )

    return run_facts, task_attempt_facts


def _build_legacy_run_fact(
    run_id: str,
    *,
    runtime_state: RunRuntimeState | None,
    run_record: RunExecutionRecord | None,
) -> OrchestrationRunFact | None:
    if runtime_state is None and run_record is None:
        return None

    runtime_active = runtime_state is not None and _runtime_is_active(runtime_state)
    if runtime_active:
        status = str(runtime_state.status)
        canonical_status_source = "runtime_state_active"
        started_at = runtime_state.started_at
        updated_at = runtime_state.updated_at
        finished_at = runtime_state.finished_at
        task_count, completed_task_count, running_task_count, failed_task_count = _runtime_task_counts(runtime_state.tasks)
        run_title = runtime_state.run_title
        source_path = str(runtime_state.run_spec_path)
        repo_root = str(runtime_state.repo_root)
        config_path = str(runtime_state.config_path)
        flow_run_name = None
    elif run_record is not None:
        status = _derive_record_run_status(run_record)
        canonical_status_source = "run_record"
        started_at = run_record.recorded_at
        updated_at = run_record.recorded_at
        finished_at = run_record.recorded_at
        task_count, completed_task_count, running_task_count, failed_task_count = _record_task_counts(run_record.tasks)
        run_title = run_record.run_title
        source_path = str(run_record.run_spec_path)
        repo_root = str(run_record.repo_root)
        config_path = str(run_record.config_path)
        flow_run_name = None
    else:
        assert runtime_state is not None
        status = "completed" if runtime_state.finished_at is not None else str(runtime_state.status)
        canonical_status_source = "runtime_state_snapshot"
        started_at = runtime_state.started_at
        updated_at = runtime_state.updated_at
        finished_at = runtime_state.finished_at
        task_count, completed_task_count, running_task_count, failed_task_count = _runtime_task_counts(runtime_state.tasks)
        run_title = runtime_state.run_title
        source_path = str(runtime_state.run_spec_path)
        repo_root = str(runtime_state.repo_root)
        config_path = str(runtime_state.config_path)
        flow_run_name = None

    task_attempt_count = 0
    if runtime_active and runtime_state is not None:
        task_attempt_count = sum(1 for task in runtime_state.tasks if task.attempts > 0)
    elif run_record is not None:
        task_attempt_count = len(run_record.tasks)
    elif runtime_state is not None:
        task_attempt_count = sum(1 for task in runtime_state.tasks if task.attempts > 0)

    return OrchestrationRunFact(
        run_fact_id=f"oats_local:{run_id}",
        run_source="oats_local",
        run_id=run_id,
        flow_run_name=flow_run_name,
        run_title=run_title,
        source_path=source_path,
        repo_root=repo_root,
        config_path=config_path,
        artifact_root=str(runtime_state.runtime_dir) if runtime_state is not None else None,
        status=status,
        canonical_status_source=canonical_status_source,
        has_runtime_snapshot=runtime_state is not None,
        has_terminal_record=run_record is not None,
        task_count=task_count,
        completed_task_count=completed_task_count,
        running_task_count=running_task_count,
        failed_task_count=failed_task_count,
        task_attempt_count=task_attempt_count,
        started_at=started_at,
        updated_at=updated_at,
        finished_at=finished_at,
    )


def _build_legacy_task_attempt_facts(
    run_fact: OrchestrationRunFact,
    *,
    runtime_state: RunRuntimeState | None,
    run_record: RunExecutionRecord | None,
) -> list[OrchestrationTaskAttemptFact]:
    if run_fact.canonical_status_source == "run_record" and run_record is not None:
        return [_record_attempt_fact(run_fact, task) for task in run_record.tasks]
    if runtime_state is not None:
        return [
            _runtime_attempt_fact(run_fact, task, fallback_updated_at=runtime_state.updated_at)
            for task in runtime_state.tasks
            if task.attempts > 0
        ]
    return []


def _record_attempt_fact(run_fact: OrchestrationRunFact, task: TaskExecutionRecord) -> OrchestrationTaskAttemptFact:
    invocation = task.invocation
    return OrchestrationTaskAttemptFact(
        task_attempt_fact_id=f"{run_fact.run_fact_id}:{task.task_id}:1",
        run_fact_id=run_fact.run_fact_id,
        run_source=run_fact.run_source,
        run_id=run_fact.run_id,
        task_id=str(task.task_id),
        task_title=task.title,
        attempt=1,
        status=_derive_invocation_task_status(invocation),
        upstream_task_ids_json=json.dumps(list(task.depends_on)),
        agent=invocation.agent,
        session_id=invocation.session_id,
        model=None,
        reasoning_effort=None,
        error=invocation.raw_stderr or None,
        output_text=invocation.output_text,
        started_at=invocation.started_at,
        updated_at=invocation.finished_at,
        finished_at=invocation.finished_at,
        last_heartbeat_at=getattr(invocation, "last_heartbeat_at", None),
        last_progress_event_at=None,
    )


def _runtime_attempt_fact(
    run_fact: OrchestrationRunFact,
    task: TaskRuntimeRecord,
    *,
    fallback_updated_at: datetime,
) -> OrchestrationTaskAttemptFact:
    invocation = task.invocation
    updated_at = (
        invocation.last_progress_event_at
        if invocation is not None and invocation.last_progress_event_at is not None
        else invocation.last_heartbeat_at
        if invocation is not None and invocation.last_heartbeat_at is not None
        else fallback_updated_at
    )
    return OrchestrationTaskAttemptFact(
        task_attempt_fact_id=f"{run_fact.run_fact_id}:{task.task_id}:{task.attempts}",
        run_fact_id=run_fact.run_fact_id,
        run_source=run_fact.run_source,
        run_id=run_fact.run_id,
        task_id=str(task.task_id),
        task_title=task.title,
        attempt=task.attempts,
        status=str(task.status),
        upstream_task_ids_json=json.dumps(list(task.depends_on)),
        agent=task.agent,
        session_id=invocation.session_id if invocation is not None else None,
        model=None,
        reasoning_effort=None,
        error=invocation.raw_stderr if invocation is not None else None,
        output_text=invocation.output_text if invocation is not None else None,
        started_at=invocation.started_at if invocation is not None else None,
        updated_at=updated_at,
        finished_at=invocation.finished_at if invocation is not None else None,
        last_heartbeat_at=invocation.last_heartbeat_at if invocation is not None else None,
        last_progress_event_at=invocation.last_progress_event_at if invocation is not None else None,
    )


def _runtime_task_counts(tasks: list[TaskRuntimeRecord]) -> tuple[int, int, int, int]:
    task_count = len(tasks)
    completed = sum(1 for task in tasks if str(task.status) in {"succeeded", "skipped"})
    running = sum(1 for task in tasks if str(task.status) in {"running", "pending", "blocked"})
    failed = sum(1 for task in tasks if str(task.status) in {"failed", "timed_out"})
    return task_count, completed, running, failed


def _record_task_counts(tasks: list[TaskExecutionRecord]) -> tuple[int, int, int, int]:
    task_count = len(tasks)
    completed = sum(1 for task in tasks if _derive_invocation_task_status(task.invocation) == "succeeded")
    failed = sum(1 for task in tasks if _derive_invocation_task_status(task.invocation) == "failed")
    return task_count, completed, 0, failed


def _derive_record_run_status(record: RunExecutionRecord) -> RunRuntimeStatus:
    if not record.tasks:
        return "completed"
    if any(_derive_invocation_task_status(task.invocation) == "failed" for task in record.tasks):
        return "failed"
    return "completed"


def _derive_invocation_task_status(
    invocation: AgentInvocationResult | InvocationRuntimeRecord,
) -> TaskRuntimeStatus:
    if invocation.timed_out:
        return "timed_out"
    if invocation.exit_code not in (None, 0):
        return "failed"
    if invocation.finished_at is None:
        return "running"
    return "succeeded"


def _runtime_is_active(state: RunRuntimeState) -> bool:
    if state.finished_at is not None or str(state.status) not in ACTIVE_RUN_STATUSES:
        return False
    heartbeat_at = state.heartbeat_at or state.updated_at
    return (_utc_now() - heartbeat_at.astimezone(UTC)).total_seconds() <= STALE_RUNTIME_AFTER_SECONDS


def _parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _result_field(result: dict[str, object] | None, key: str) -> str | None:
    if result is None:
        return None
    value = result.get(key)
    return value if isinstance(value, str) else None


def _utc_now() -> datetime:
    return datetime.now(UTC)
