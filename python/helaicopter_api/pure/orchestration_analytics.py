"""Canonical orchestration analytics facts built from file-backed OATS artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from oats.models import (
    AgentInvocationResult,
    InvocationRuntimeRecord,
    RunExecutionRecord,
    RunRuntimeState,
    TaskExecutionRecord,
    TaskRuntimeRecord,
)

ACTIVE_RUN_STATUSES = {"pending", "planning", "running"}
STALE_RUNTIME_AFTER_SECONDS = 300
CANONICAL_RULES: tuple[str, ...] = (
    "prefer fresh runtime snapshots while a run is still active",
    "prefer terminal run records when runtime snapshots are stale or missing",
    "emit one task-attempt fact for the latest observed runtime attempt when history is incomplete",
    "emit one terminal task-attempt fact per recorded task invocation with attempt number 1",
)


@dataclass(frozen=True, slots=True)
class OrchestrationRunFact:
    """Fact grain: one canonical row per OATS run identifier."""

    run_id: str
    run_title: str
    source_kind: Literal["runtime_snapshot", "terminal_record"]
    canonical_reason: str
    status: str
    task_count: int
    attempt_count: int
    completed_task_count: int
    failed_task_count: int
    pending_task_count: int
    running_task_count: int
    timed_out_task_count: int
    active_task_id: str | None
    is_running: bool
    is_stale: bool
    runtime_state_path: str | None
    terminal_record_path: str | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class OrchestrationTaskAttemptFact:
    """Fact grain: one row per observed task attempt within a canonical run source."""

    run_id: str
    task_id: str
    task_title: str
    attempt_number: int
    source_kind: Literal["runtime_snapshot", "terminal_record"]
    status: str
    agent: str | None
    session_id: str | None
    exit_code: int | None
    timed_out: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class OrchestrationAnalyticsFacts:
    canonical_rules: tuple[str, ...] = field(default_factory=lambda: CANONICAL_RULES)
    run_facts: list[OrchestrationRunFact] = field(default_factory=list)
    task_attempt_facts: list[OrchestrationTaskAttemptFact] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "canonical_rules": list(self.canonical_rules),
            "run_facts": [fact.to_dict() for fact in self.run_facts],
            "task_attempt_facts": [fact.to_dict() for fact in self.task_attempt_facts],
        }


@dataclass(frozen=True, slots=True)
class StoredRuntimeArtifact:
    path: Path
    state: RunRuntimeState


@dataclass(frozen=True, slots=True)
class StoredTerminalArtifact:
    path: Path
    record: RunExecutionRecord


def build_oats_orchestration_facts(
    runtime_states: list[StoredRuntimeArtifact],
    run_records: list[StoredTerminalArtifact],
    *,
    now: datetime | None = None,
) -> OrchestrationAnalyticsFacts:
    current_time = _coerce_datetime(now or datetime.now(UTC))
    runtime_by_run_id = {item.state.run_id: item for item in runtime_states}
    record_by_run_id = {item.record.run_id or item.path.stem: item for item in run_records}
    run_ids = sorted({*runtime_by_run_id, *record_by_run_id})

    run_facts: list[OrchestrationRunFact] = []
    task_attempt_facts: list[OrchestrationTaskAttemptFact] = []

    for run_id in run_ids:
        runtime_item = runtime_by_run_id.get(run_id)
        terminal_item = record_by_run_id.get(run_id)
        selected_source = _select_canonical_source(runtime_item, terminal_item, now=current_time)
        run_fact = _build_run_fact(
            run_id=run_id,
            runtime_item=runtime_item,
            terminal_item=terminal_item,
            selected_source=selected_source,
            now=current_time,
        )
        run_facts.append(run_fact)
        task_attempt_facts.extend(
            _build_task_attempt_facts(
                run_id=run_id,
                runtime_item=runtime_item,
                terminal_item=terminal_item,
                source_kind=selected_source,
                now=current_time,
            )
        )

    return OrchestrationAnalyticsFacts(run_facts=run_facts, task_attempt_facts=task_attempt_facts)


def _select_canonical_source(
    runtime_item: StoredRuntimeArtifact | None,
    terminal_item: StoredTerminalArtifact | None,
    *,
    now: datetime,
) -> Literal["runtime_snapshot", "terminal_record"]:
    if runtime_item is None:
        return "terminal_record"
    if terminal_item is None:
        return "runtime_snapshot"

    runtime = runtime_item.state
    if not _is_stale_runtime_state(runtime, now=now):
        return "runtime_snapshot"
    return "terminal_record"


def _build_run_fact(
    *,
    run_id: str,
    runtime_item: StoredRuntimeArtifact | None,
    terminal_item: StoredTerminalArtifact | None,
    selected_source: Literal["runtime_snapshot", "terminal_record"],
    now: datetime,
) -> OrchestrationRunFact:
    runtime_state_path = str(runtime_item.path) if runtime_item is not None else None
    terminal_record_path = str(terminal_item.path) if terminal_item is not None else None
    runtime_is_stale = runtime_item is not None and _is_stale_runtime_state(runtime_item.state, now=now)

    if selected_source == "runtime_snapshot" and runtime_item is not None:
        runtime = runtime_item.state
        task_statuses = [_reconcile_runtime_task_status(task, stale=runtime_is_stale) for task in runtime.tasks]
        return OrchestrationRunFact(
            run_id=run_id,
            run_title=runtime.run_title,
            source_kind="runtime_snapshot",
            canonical_reason="runtime snapshot is active and fresher than any terminal record",
            status=_reconcile_runtime_run_status(runtime, task_statuses, stale=runtime_is_stale),
            task_count=len(runtime.tasks),
            attempt_count=sum(task.attempts for task in runtime.tasks),
            completed_task_count=sum(1 for status in task_statuses if status == "succeeded"),
            failed_task_count=sum(1 for status in task_statuses if status == "failed"),
            pending_task_count=sum(1 for status in task_statuses if status == "pending"),
            running_task_count=sum(1 for status in task_statuses if status == "running"),
            timed_out_task_count=sum(1 for status in task_statuses if status == "timed_out"),
            active_task_id=None if runtime_is_stale else runtime.active_task_id,
            is_running=not runtime_is_stale and runtime.status in ACTIVE_RUN_STATUSES and runtime.finished_at is None,
            is_stale=runtime_is_stale,
            runtime_state_path=runtime_state_path,
            terminal_record_path=terminal_record_path,
        )

    if terminal_item is None:
        raise ValueError("terminal record is required when runtime is not selected")
    record = terminal_item.record
    task_statuses = [_derive_terminal_task_status(task) for task in record.tasks]
    return OrchestrationRunFact(
        run_id=run_id,
        run_title=record.run_title,
        source_kind="terminal_record",
        canonical_reason=(
            "terminal record wins because the runtime snapshot is stale"
            if runtime_item is not None
            else "terminal record is the only artifact available for the run"
        ),
        status=_derive_terminal_run_status(record),
        task_count=len(record.tasks),
        attempt_count=len(record.tasks),
        completed_task_count=sum(1 for status in task_statuses if status == "succeeded"),
        failed_task_count=sum(1 for status in task_statuses if status == "failed"),
        pending_task_count=sum(1 for status in task_statuses if status == "pending"),
        running_task_count=sum(1 for status in task_statuses if status == "running"),
        timed_out_task_count=sum(1 for status in task_statuses if status == "timed_out"),
        active_task_id=None,
        is_running=False,
        is_stale=runtime_is_stale,
        runtime_state_path=runtime_state_path,
        terminal_record_path=terminal_record_path,
    )


def _build_task_attempt_facts(
    *,
    run_id: str,
    runtime_item: StoredRuntimeArtifact | None,
    terminal_item: StoredTerminalArtifact | None,
    source_kind: Literal["runtime_snapshot", "terminal_record"],
    now: datetime,
) -> list[OrchestrationTaskAttemptFact]:
    if source_kind == "runtime_snapshot":
        if runtime_item is None:
            return []
        stale = _is_stale_runtime_state(runtime_item.state, now=now)
        facts: list[OrchestrationTaskAttemptFact] = []
        for task in runtime_item.state.tasks:
            if task.attempts <= 0 and task.invocation is None:
                continue
            invocation = task.invocation
            facts.append(
                OrchestrationTaskAttemptFact(
                    run_id=run_id,
                    task_id=task.task_id,
                    task_title=task.title,
                    attempt_number=max(task.attempts, 1),
                    source_kind="runtime_snapshot",
                    status=_reconcile_runtime_task_status(task, stale=stale),
                    agent=task.agent,
                    session_id=invocation.session_id if invocation is not None else None,
                    exit_code=invocation.exit_code if invocation is not None else None,
                    timed_out=invocation.timed_out if invocation is not None else False,
                )
            )
        return facts

    if terminal_item is None:
        return []
    return [
        OrchestrationTaskAttemptFact(
            run_id=run_id,
            task_id=task.task_id,
            task_title=task.title,
            attempt_number=1,
            source_kind="terminal_record",
            status=_derive_terminal_task_status(task),
            agent=task.invocation.agent,
            session_id=task.invocation.session_id,
            exit_code=task.invocation.exit_code,
            timed_out=task.invocation.timed_out,
        )
        for task in terminal_item.record.tasks
    ]


def _derive_terminal_task_status(task: TaskExecutionRecord) -> str:
    return _derive_invocation_status(task.invocation)


def _derive_terminal_run_status(record: RunExecutionRecord) -> str:
    if record.planner is not None:
        planner_status = _derive_invocation_status(record.planner)
        if planner_status in {"failed", "timed_out"}:
            return planner_status
    task_statuses = [_derive_terminal_task_status(task) for task in record.tasks]
    if "timed_out" in task_statuses:
        return "timed_out"
    if "failed" in task_statuses:
        return "failed"
    if "running" in task_statuses:
        return "running"
    if "pending" in task_statuses:
        return "pending"
    return "completed"


def _derive_invocation_status(invocation: AgentInvocationResult | InvocationRuntimeRecord) -> str:
    if invocation.timed_out:
        return "timed_out"
    if invocation.exit_code == 0 and invocation.finished_at is not None:
        return "succeeded"
    if invocation.exit_code not in (None, 0):
        return "failed"
    if invocation.finished_at is None and invocation.started_at is not None:
        return "running"
    return "pending"


def _reconcile_runtime_task_status(task: TaskRuntimeRecord, *, stale: bool) -> str:
    if stale and task.status == "running":
        return "pending"
    return task.status


def _reconcile_runtime_run_status(
    state: RunRuntimeState,
    task_statuses: list[str],
    *,
    stale: bool,
) -> str:
    if not stale:
        return state.status
    if any(status in {"pending", "blocked"} for status in task_statuses):
        return "pending"
    if any(status == "timed_out" for status in task_statuses):
        return "timed_out"
    if any(status == "failed" for status in task_statuses):
        return "failed"
    return "completed"


def _is_stale_runtime_state(state: RunRuntimeState, *, now: datetime) -> bool:
    if state.finished_at is not None or state.status not in ACTIVE_RUN_STATUSES:
        return False
    if state.active_task_id is None and not any(task.status == "running" for task in state.tasks):
        return False
    heartbeat_age = (now - _coerce_datetime(state.heartbeat_at)).total_seconds()
    return heartbeat_age > STALE_RUNTIME_AFTER_SECONDS


def _coerce_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
