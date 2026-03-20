from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, cast
from pathlib import Path
import json
import shlex
import subprocess
import time

import typer
from helaicopter_domain.ids import TaskId
from helaicopter_domain.vocab import RunRuntimeStatus
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from oats.parser import RunSpecParseError, parse_run_spec
from oats.planner import PlanError, build_execution_plan
from oats.prefect.client import PrefectApiError
from oats.prefect.deployments import (
    deploy_run_spec,
    read_flow_run_status,
    trigger_run_spec,
)
from oats.repo_config import RepoConfigError, find_repo_config, load_repo_config
from oats.runner import (
    AgentInvocationError,
    InvocationProgress,
    build_planner_prompt,
    build_task_prompt,
    invoke_agent,
)
from oats.models import (
    AgentInvocationResult,
    ExecutionPlan,
    FinalPullRequestSnapshot,
    InvocationRuntimeRecord,
    RepoConfig,
    RunExecutionRecord,
    RunRuntimeState,
    TaskPullRequestSnapshot,
    TaskExecutionRecord,
)
from oats.pr import (
    build_final_pr_plan,
    build_integration_branch_commands,
    build_pr_create_command,
    build_final_pr_title,
    build_task_pr_plans,
    execute_pr_plan,
    refresh_run,
    resume_run as resume_stacked_pr_run,
)
from oats.runtime_state import (
    append_progress_event,
    apply_agent_result,
    build_initial_runtime_state,
    build_plan_snapshot,
    build_run_id,
    mark_run_finished,
    mark_run_resumed,
    mark_run_started,
    prepare_invocation_runtime,
    record_invocation_heartbeat,
    record_invocation_progress,
    resolve_runtime_state,
    write_plan_snapshot,
    write_runtime_state,
)
from oats.run_definition_loader import (
    UnsupportedRunDefinitionInputError,
    load_run_definition,
)


app = typer.Typer(
    help=(
        "Overnight Oats CLI. Primary path: prefect deploy, run, status. "
        "Legacy top-level commands available."
    )
)
prefect_app = typer.Typer(help="Primary orchestration commands: deploy, run, status.")
app.add_typer(prefect_app, name="prefect")
console = Console()
DEFAULT_STALE_AFTER_SECONDS = 300
DEFAULT_PROGRESS_HEARTBEAT_INTERVAL_SECONDS = 30.0


def _load_execution_plan(
    run_spec: Path,
    repo: Path | None,
) -> tuple[RepoConfig, Path, ExecutionPlan]:
    search_root = repo.resolve() if repo else run_spec.resolve().parent
    config_path = find_repo_config(search_root)
    config = load_repo_config(config_path)
    run_model = parse_run_spec(run_spec.resolve())
    execution_plan = build_execution_plan(
        config=config,
        run_spec=run_model,
        repo_root=config_path.parent.parent,
        config_path=config_path,
    )
    return config, config_path, execution_plan


def _load_repo_config_for_run_spec(
    run_spec: Path,
    repo: Path | None,
) -> tuple[RepoConfig, Path]:
    search_root = repo.resolve() if repo else run_spec.resolve().parent
    config_path = find_repo_config(search_root)
    return load_repo_config(config_path), config_path


def _invocation_runtime_to_result(
    invocation: InvocationRuntimeRecord | None,
) -> AgentInvocationResult | None:
    if invocation is None or invocation.started_at is None or invocation.finished_at is None:
        return None
    return AgentInvocationResult(
        agent=invocation.agent,
        role=invocation.role,
        command=invocation.command,
        cwd=invocation.cwd,
        prompt=invocation.prompt,
        session_id=invocation.session_id,
        session_id_field=invocation.session_id_field,
        requested_session_id=invocation.requested_session_id,
        output_text=invocation.output_text,
        raw_stdout=invocation.raw_stdout,
        raw_stderr=invocation.raw_stderr,
        exit_code=invocation.exit_code or 0,
        timed_out=invocation.timed_out,
        started_at=invocation.started_at,
        finished_at=invocation.finished_at,
    )


def _build_task_records_from_runtime(state: RunRuntimeState) -> list[TaskExecutionRecord]:
    task_records: list[TaskExecutionRecord] = []
    for task in state.tasks:
        invocation = _invocation_runtime_to_result(task.invocation)
        if invocation is None:
            continue
        task_records.append(
            TaskExecutionRecord(
                task_id=task.task_id,
                title=task.title,
                depends_on=task.depends_on,
                invocation=invocation,
            )
        )
    return task_records


def _print_execution_record(record: RunExecutionRecord, runtime_state: RunRuntimeState) -> None:
    console.print(
        Panel.fit(
            f"Run: [bold]{record.run_title}[/bold]\n"
            f"Run ID: {record.run_id}\n"
            f"Repo: {record.repo_root}\n"
            f"Integration branch: {record.integration_branch}\n"
            f"Task PR target: {record.task_pr_target}\n"
            f"Final PR target: {record.final_pr_target}\n"
            f"Runtime state: {runtime_state.runtime_dir / 'state.json'}\n"
            f"Record: {record.record_path}",
            title="Execution Record",
        )
    )

    table = Table(show_header=True, header_style="bold")
    table.add_column("Role")
    table.add_column("Agent")
    table.add_column("Session Field")
    table.add_column("Session ID")
    table.add_column("Exit")
    table.add_column("Timed Out")

    if record.planner:
        table.add_row(
            "planner",
            record.planner.agent,
            record.planner.session_id_field or "-",
            record.planner.session_id or "-",
            str(record.planner.exit_code),
            "yes" if record.planner.timed_out else "no",
        )
    for task in record.tasks:
        table.add_row(
            f"executor:{task.task_id}",
            task.invocation.agent,
            task.invocation.session_id_field or "-",
            task.invocation.session_id or "-",
            str(task.invocation.exit_code),
            "yes" if task.invocation.timed_out else "no",
        )

    console.print(table)


def _resolve_terminal_status(state: RunRuntimeState) -> RunRuntimeStatus:
    task_statuses = {task.status for task in state.tasks}
    if state.status in {"failed", "timed_out"}:
        return state.status
    if "running" in task_statuses:
        return "running"
    if "timed_out" in task_statuses:
        return "timed_out"
    if "failed" in task_statuses:
        return "failed"
    if task_statuses and task_statuses.issubset({"succeeded", "skipped"}):
        return "completed"
    if {"pending", "blocked"} & task_statuses:
        return "pending"
    return state.status


def _active_invocation(state: RunRuntimeState):
    if state.active_task_id:
        task = _find_runtime_task(state, state.active_task_id)
        return task.invocation, f"task:{task.task_id}", task.task_id
    if state.planner is not None and state.status in {"planning", "running"}:
        return state.planner, "planner", None
    return None, None, None


def _runtime_health(
    state: RunRuntimeState,
    *,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
    now: datetime | None = None,
) -> str:
    if state.finished_at is not None or state.status in {"completed", "failed", "timed_out"}:
        return state.status
    if state.status not in {"pending", "planning", "running"}:
        return state.status

    reference_time = now or datetime.now(timezone.utc)
    heartbeat_age = (reference_time - state.heartbeat_at).total_seconds()
    if (state.active_task_id is not None or _has_unfinished_tasks(state)) and heartbeat_age > stale_after_seconds:
        return "stale"
    return "healthy"


def _format_duration(seconds: float) -> str:
    total_seconds = max(int(seconds), 0)
    minutes, seconds_part = divmod(total_seconds, 60)
    hours, minutes_part = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes_part}m {seconds_part}s"
    if minutes:
        return f"{minutes}m {seconds_part}s"
    return f"{seconds_part}s"


def _build_runtime_status_text(
    state: RunRuntimeState,
    *,
    state_path: Path,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
) -> str:
    now = datetime.now(timezone.utc)
    health = _runtime_health(state, stale_after_seconds=stale_after_seconds, now=now)
    heartbeat_age = _format_duration((now - state.heartbeat_at).total_seconds())
    invocation, invocation_label, task_id = _active_invocation(state)
    latest_note = "-"
    session_id = "-"
    if invocation is not None:
        session_id = invocation.session_id or "-"
        latest_note = " ".join(invocation.output_text.split())[:240] or "-"

    lines = [
        f"Run: [bold]{state.run_title}[/bold]",
        f"Run ID: {state.run_id}",
        f"Status: {state.status}",
        f"Stack status: {state.stack_status}",
        f"Feature branch: {state.feature_branch.name if state.feature_branch else state.integration_branch}",
        f"Final PR: {state.final_pr.state}",
        f"Health: {health}",
        f"Active task: {task_id or '-'}",
        f"Heartbeat age: {heartbeat_age}",
        f"Runtime state: {state_path}",
    ]
    if invocation_label is not None:
        lines.append(f"Active invocation: {invocation_label}")
        lines.append(f"Session ID: {session_id}")
    lines.append(f"Latest note: {latest_note}")
    return "\n".join(lines)


def _print_runtime_status(
    state: RunRuntimeState,
    *,
    state_path: Path,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
) -> None:
    console.print(
        Panel.fit(
            _build_runtime_status_text(
                state,
                state_path=state_path,
                stale_after_seconds=stale_after_seconds,
            ),
            title="Runtime Status",
        )
    )


def _handle_runtime_heartbeat(
    state: RunRuntimeState,
    invocation: InvocationRuntimeRecord | None,
    *,
    event_type: str,
    task_id: str | None = None,
) -> None:
    record_invocation_heartbeat(
        state,
        invocation,
        event_type=event_type,
        task_id=task_id,
        min_interval_seconds=DEFAULT_PROGRESS_HEARTBEAT_INTERVAL_SECONDS,
    )


def _handle_runtime_progress(
    state: RunRuntimeState,
    invocation: InvocationRuntimeRecord | None,
    *,
    event_type: str,
    task_id: str | None = None,
    progress: InvocationProgress,
) -> None:
    record_invocation_progress(
        state,
        invocation,
        event_type=event_type,
        task_id=task_id,
        **progress,
    )


def _prepare_retryable_tasks(state: RunRuntimeState) -> bool:
    reset_any = False
    for task in state.tasks:
        if task.status in {"failed", "timed_out", "blocked", "running"} or (
            task.status == "pending" and task.attempts > 0
        ):
            task.status = "pending"
            task.attempts = 0
            reset_any = True
    if reset_any:
        state.status = "pending"
        state.active_task_id = None
        state.finished_at = None
        state.final_record_path = None
    return reset_any


def _find_runtime_task(state: RunRuntimeState, task_id: str):
    return next(item for item in state.tasks if item.task_id == task_id)


class _GhCliClient:
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root

    def read_task_pr(self, task) -> TaskPullRequestSnapshot:
        if task.task_pr.number is None:
            return task.task_pr
        payload = self._read_pr_json(task.task_pr.number)
        return _task_snapshot_from_payload(payload)

    def merge_task_pr(
        self,
        task,
        snapshot: TaskPullRequestSnapshot,
        *,
        merge_method: str,
    ) -> TaskPullRequestSnapshot:
        if snapshot.number is None:
            return snapshot
        if merge_method != "merge_commit":
            raise RuntimeError(f"Unsupported merge method: {merge_method}")
        completed = self._run("pr", "merge", str(snapshot.number), "--merge")
        if completed.returncode != 0:
            stderr = (completed.stderr or "").lower()
            if "conflict" in stderr or "not mergeable" in stderr:
                from oats.pr import PullRequestMergeConflictError

                raise PullRequestMergeConflictError(completed.stderr.strip() or completed.stdout.strip())
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
        return self.read_task_pr(task)

    def retarget_task_pr(self, task, *, base_branch: str) -> TaskPullRequestSnapshot:
        if task.task_pr.number is None:
            return task.task_pr.model_copy(update={"base_branch": base_branch}, deep=True)
        completed = self._run("pr", "edit", str(task.task_pr.number), "--base", base_branch)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
        return self.read_task_pr(task)

    def create_final_pr(self, state: RunRuntimeState) -> FinalPullRequestSnapshot:
        completed = self._run(
            "pr",
            "create",
            "--base",
            state.final_pr_target,
            "--head",
            state.feature_branch.name if state.feature_branch else state.integration_branch,
            "--title",
            build_final_pr_title(state.run_title),
            "--body",
            f"Final Overnight Oats review PR for `{state.run_title}`.",
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
        identifier = completed.stdout.strip().splitlines()[-1]
        payload = self._read_pr_json(identifier)
        return _final_snapshot_from_payload(payload)

    def read_final_pr(self, state: RunRuntimeState) -> FinalPullRequestSnapshot:
        identifier = (
            str(state.final_pr.number)
            if state.final_pr.number is not None
            else state.final_pr.url
            or (state.feature_branch.name if state.feature_branch else state.integration_branch)
        )
        completed = self._run(
            "pr",
            "view",
            str(identifier),
            "--json",
            "number,url,state,baseRefName,headRefName,mergeable,reviewDecision,statusCheckRollup,mergedAt,updatedAt",
        )
        if completed.returncode != 0 and state.final_pr.state == "not_created":
            return state.final_pr
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
        payload = cast(dict[str, object], json.loads(completed.stdout))
        return _final_snapshot_from_payload(payload)

    def _read_pr_json(self, identifier: str | int) -> dict[str, object]:
        completed = self._run(
            "pr",
            "view",
            str(identifier),
            "--json",
            "number,url,state,baseRefName,headRefName,mergeable,reviewDecision,statusCheckRollup,mergedAt,updatedAt",
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
        return cast(dict[str, object], json.loads(completed.stdout))

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["gh", *args],
            cwd=self._repo_root,
            capture_output=True,
            text=True,
            check=False,
        )


def _task_snapshot_from_payload(payload: dict[str, object]) -> TaskPullRequestSnapshot:
    state = _normalize_pr_state(payload.get("state"), payload.get("mergedAt"))
    review_decision = str(payload.get("reviewDecision") or "").upper()
    checks_state = _checks_summary_from_rollup(payload.get("statusCheckRollup"))
    if state == "merged":
        merge_gate_status = "merged"
    elif review_decision == "CHANGES_REQUESTED":
        merge_gate_status = "awaiting_review_clearance"
    elif checks_state["state"] == "success":
        merge_gate_status = "merge_ready"
    elif checks_state["state"] == "pending":
        merge_gate_status = "awaiting_checks"
    else:
        merge_gate_status = "not_ready"
    return TaskPullRequestSnapshot(
        number=cast(int | None, payload.get("number")),
        url=cast(str | None, payload.get("url")),
        state=cast(
            Literal["not_created", "open", "merged", "closed", "blocked"],
            state,
        ),
        merge_gate_status=cast(
            Literal[
                "not_ready",
                "awaiting_checks",
                "awaiting_review_clearance",
                "merge_ready",
                "merged",
            ],
            merge_gate_status,
        ),
        base_branch=cast(str | None, payload.get("baseRefName")),
        head_branch=cast(str | None, payload.get("headRefName")),
        mergeability=cast(str | None, payload.get("mergeable")),
        checks_summary=checks_state,
        review_summary={
            "blocking_state": "changes_requested"
            if review_decision == "CHANGES_REQUESTED"
            else "clear"
        },
        snapshot_source="github_cli",
        last_refreshed_at=datetime.now(timezone.utc),
    )


def _final_snapshot_from_payload(payload: dict[str, object]) -> FinalPullRequestSnapshot:
    state = _normalize_pr_state(payload.get("state"), payload.get("mergedAt"))
    return FinalPullRequestSnapshot(
        number=cast(int | None, payload.get("number")),
        url=cast(str | None, payload.get("url")),
        state=cast(
            Literal["not_created", "open", "ready_for_review", "merged", "closed"],
            "merged" if state == "merged" else "open" if state == "open" else "closed",
        ),
        review_gate_status=cast(
            Literal["not_created", "awaiting_human", "merged"],
            "merged" if state == "merged" else "awaiting_human",
        ),
        base_branch=cast(str | None, payload.get("baseRefName")),
        head_branch=cast(str | None, payload.get("headRefName")),
        checks_summary=_checks_summary_from_rollup(payload.get("statusCheckRollup")),
        snapshot_source="github_cli",
        last_refreshed_at=datetime.now(timezone.utc),
    )


def _normalize_pr_state(raw_state: object, merged_at: object) -> str:
    normalized = str(raw_state or "").upper()
    if merged_at:
        return "merged"
    if normalized == "OPEN":
        return "open"
    if normalized == "MERGED":
        return "merged"
    if normalized == "CLOSED":
        return "closed"
    return "not_created"


def _checks_summary_from_rollup(rollup: object) -> dict[str, object]:
    if not isinstance(rollup, list) or not rollup:
        return {"state": "unknown"}
    normalized_states = []
    for item in rollup:
        if not isinstance(item, dict):
            continue
        normalized_states.append(
            str(
                item.get("conclusion")
                or item.get("state")
                or item.get("status")
                or "unknown"
            ).upper()
        )
    if any(state in {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED"} for state in normalized_states):
        return {"state": "failure"}
    if any(state in {"PENDING", "IN_PROGRESS", "EXPECTED", "QUEUED"} for state in normalized_states):
        return {"state": "pending"}
    if normalized_states and all(
        state in {"SUCCESS", "NEUTRAL", "SKIPPED"} for state in normalized_states
    ):
        return {"state": "success"}
    return {"state": "unknown"}


def _refresh_task_readiness(state: RunRuntimeState) -> bool:
    progressed = False
    for runtime_task in state.tasks:
        if runtime_task.status in {"succeeded", "failed", "timed_out", "skipped", "running"}:
            continue
        deps_satisfied = all(
            _find_runtime_task(state, dep).status == "succeeded"
            for dep in runtime_task.depends_on
        )
        desired_status = "pending" if deps_satisfied else "blocked"
        if runtime_task.status != desired_status:
            runtime_task.status = desired_status
            progressed = True
    return progressed


def _has_unfinished_tasks(state: RunRuntimeState) -> bool:
    return any(task.status in {"pending", "blocked", "running"} for task in state.tasks)


def _is_transient_failure(result: AgentInvocationResult) -> bool:
    haystacks = [
        result.output_text.lower(),
        result.raw_stdout.lower(),
        result.raw_stderr.lower(),
    ]
    transient_markers = (
        "internal server error",
        '"type":"api_error"',
        '"type":"rate_limit_error"',
        "rate limit",
        "temporarily unavailable",
        "connection reset",
        "connection aborted",
        "upstream connect error",
        "timeout",
    )
    return result.timed_out or any(
        marker in haystack for haystack in haystacks for marker in transient_markers
    )


def _persist_run_record_and_state(
    *,
    execution_plan: ExecutionPlan,
    record: RunExecutionRecord,
    runtime_state: RunRuntimeState,
) -> None:
    runs_dir = execution_plan.repo_root / ".oats" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    record_name = f"{execution_plan.run_spec_path.stem}-{record.recorded_at.strftime('%Y%m%dT%H%M%SZ')}.json"
    record_path = runs_dir / record_name
    record.record_path = record_path
    record_path.write_text(record.model_dump_json(indent=2))
    status = _resolve_terminal_status(runtime_state)
    if status in {"completed", "failed", "timed_out"}:
        mark_run_finished(runtime_state, status=status, final_record_path=record_path)
        append_progress_event(runtime_state, event_type="run_finished", message=status)
    else:
        runtime_state.status = status
        runtime_state.updated_at = record.recorded_at
        runtime_state.final_record_path = record_path
    write_runtime_state(runtime_state)


def _execute_run(
    *,
    config: RepoConfig,
    execution_plan: ExecutionPlan,
    read_only: bool,
    timeout_seconds: int,
    dangerous_bypass: bool,
    skip_planner: bool,
    runtime_state: RunRuntimeState | None = None,
) -> tuple[RunExecutionRecord, RunRuntimeState]:
    mode: Literal["read-only", "writable"] = "read-only" if read_only else "writable"
    effective_dangerous_bypass = dangerous_bypass or (
        not read_only and config.execution.dangerous_bypass
    )
    state = runtime_state or build_initial_runtime_state(
        execution_plan,
        mode=mode,
        run_id=build_run_id(execution_plan.run_spec_path),
        executor_agent=config.agents.executor,
    )
    state.mode = mode

    write_plan_snapshot(build_plan_snapshot(state, execution_plan), state.runtime_dir)
    if runtime_state is None:
        mark_run_started(state)
        append_progress_event(state, event_type="run_started")
    else:
        mark_run_resumed(state)
        append_progress_event(state, event_type="run_resumed")
    write_runtime_state(state)

    planner_result: AgentInvocationResult | None = _invocation_runtime_to_result(state.planner)
    if skip_planner and planner_result is None:
        state.status = "running"
        append_progress_event(
            state,
            event_type="planner_skipped",
            message="Execution used the persisted plan directly.",
        )
        write_runtime_state(state)
    elif planner_result is None:
        planner_prompt = build_planner_prompt(
            execution_plan.run_title,
            execution_plan.tasks,
            read_only=read_only,
        )
        state.planner = prepare_invocation_runtime(
            agent=config.agents.planner,
            role="planner",
            cwd=execution_plan.repo_root,
            prompt=planner_prompt,
        )
        append_progress_event(state, event_type="planner_started")
        write_runtime_state(state)
        planner_result = invoke_agent(
            agent_name=config.agents.planner,
            agent_command=config.agent[config.agents.planner],
            role="planner",
            cwd=execution_plan.repo_root,
            prompt=planner_prompt,
            read_only=read_only,
            timeout_seconds=timeout_seconds,
            dangerous_bypass=effective_dangerous_bypass,
            raise_on_nonzero=False,
            on_heartbeat=lambda: _handle_runtime_heartbeat(
                state,
                state.planner,
                event_type="planner_heartbeat",
            ),
            on_progress=lambda progress: _handle_runtime_progress(
                state,
                state.planner,
                event_type="planner_progress",
                progress=progress,
            ),
        )
        apply_agent_result(state.planner, planner_result)
        if planner_result.exit_code == 0 and not planner_result.timed_out:
            state.status = "running"
        elif planner_result.timed_out:
            state.status = "timed_out"
        else:
            state.status = "failed"
        append_progress_event(
            state,
            event_type="planner_finished",
            message=(
                "timed out"
                if planner_result.timed_out
                else f"exit_code={planner_result.exit_code}"
            ),
        )
        write_runtime_state(state)
        if state.status in {"failed", "timed_out"}:
            record = RunExecutionRecord(
                run_id=state.run_id,
                run_title=execution_plan.run_title,
                repo_root=execution_plan.repo_root,
                config_path=execution_plan.config_path,
                run_spec_path=execution_plan.run_spec_path,
                mode=mode,
                planner=planner_result,
                integration_branch=execution_plan.integration_branch,
                task_pr_target=execution_plan.task_pr_target,
                final_pr_target=execution_plan.final_pr_target,
                tasks=[],
            )
            return record, state

    while True:
        progress_made = _refresh_task_readiness(state)
        runnable_tasks = [
            task for task in execution_plan.tasks
            if _find_runtime_task(state, task.id).status == "pending"
        ]
        if not runnable_tasks:
            break

        for task in runnable_tasks:
            runtime_task = _find_runtime_task(state, task.id)
            task_prompt = build_task_prompt(task, execution_plan.run_title, read_only=read_only)
            while runtime_task.attempts < config.execution.max_task_attempts:
                runtime_task.status = "running"
                state.status = "running"
                state.active_task_id = cast(TaskId, task.id)
                runtime_task.attempts += 1
                task_agent = task.agent
                runtime_task.invocation = prepare_invocation_runtime(
                    agent=task_agent,
                    role="executor",
                    cwd=execution_plan.repo_root,
                    prompt=task_prompt,
                )
                append_progress_event(
                    state,
                    event_type="task_started",
                    task_id=task.id,
                    message=f"attempt={runtime_task.attempts}",
                )
                write_runtime_state(state)
                result = invoke_agent(
                    agent_name=task_agent,
                    agent_command=config.agent[task_agent],
                    role="executor",
                    cwd=execution_plan.repo_root,
                    prompt=task_prompt,
                    read_only=read_only,
                    timeout_seconds=timeout_seconds,
                    dangerous_bypass=effective_dangerous_bypass,
                    model=task.model,
                    reasoning_effort=task.reasoning_effort,
                    raise_on_nonzero=False,
                    on_heartbeat=lambda inv=runtime_task.invocation, task_id=task.id: _handle_runtime_heartbeat(
                        state,
                        inv,
                        event_type="task_heartbeat",
                        task_id=task_id,
                    ),
                    on_progress=lambda progress, inv=runtime_task.invocation, task_id=task.id: _handle_runtime_progress(
                        state,
                        inv,
                        event_type="task_progress",
                        task_id=task_id,
                        progress=progress,
                    ),
                )
                apply_agent_result(runtime_task.invocation, result)
                if result.exit_code == 0 and not result.timed_out:
                    runtime_task.status = "succeeded"
                    append_progress_event(
                        state,
                        event_type="task_finished",
                        task_id=task.id,
                        message=f"exit_code={result.exit_code}",
                    )
                    write_runtime_state(state)
                    state.active_task_id = None
                    progress_made = True
                    break

                transient = _is_transient_failure(result)
                attempts_left = config.execution.max_task_attempts - runtime_task.attempts
                if transient and attempts_left > 0:
                    runtime_task.status = "pending"
                    append_progress_event(
                        state,
                        event_type="task_retry_scheduled",
                        task_id=task.id,
                        message=(
                            f"attempt={runtime_task.attempts} retrying after transient failure"
                        ),
                    )
                    write_runtime_state(state)
                    time.sleep(config.execution.retry_backoff_seconds)
                    continue

                if result.timed_out:
                    runtime_task.status = "timed_out"
                    state.status = "timed_out"
                else:
                    runtime_task.status = "failed"
                    state.status = "failed"
                append_progress_event(
                    state,
                    event_type="task_finished",
                    task_id=task.id,
                    message=(
                        "timed out" if result.timed_out else f"exit_code={result.exit_code}"
                    ),
                )
                write_runtime_state(state)
                break

            if runtime_task.status in {"timed_out", "failed"}:
                break
        if state.status in {"timed_out", "failed"}:
            break
        if not progress_made and not any(
            _find_runtime_task(state, task.id).status == "pending"
            for task in execution_plan.tasks
        ):
            break

    if state.status not in {"failed", "timed_out"} and _has_unfinished_tasks(state):
        state.status = "pending"
    elif state.status not in {"failed", "timed_out"}:
        state.status = "completed"

    task_records = _build_task_records_from_runtime(state)
    record = RunExecutionRecord(
        run_id=state.run_id,
        run_title=execution_plan.run_title,
        repo_root=execution_plan.repo_root,
        config_path=execution_plan.config_path,
        run_spec_path=execution_plan.run_spec_path,
        mode=mode,
        planner=planner_result,
        integration_branch=execution_plan.integration_branch,
        task_pr_target=execution_plan.task_pr_target,
        final_pr_target=execution_plan.final_pr_target,
        tasks=task_records,
    )
    return record, state


@app.callback()
def callback() -> None:
    """Overnight Oats CLI."""


@app.command()
def plan(
    run_spec: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    repo: Path | None = typer.Option(
        None,
        "--repo",
        file_okay=False,
        dir_okay=True,
        help="Repo root to use when resolving .oats/config.toml.",
    ),
) -> None:
    """Parse a Markdown run spec and print the resolved plan."""

    search_root = repo.resolve() if repo else run_spec.resolve().parent

    try:
        config_path = find_repo_config(search_root)
        config = load_repo_config(config_path)
        run = parse_run_spec(run_spec.resolve())
        execution_plan = build_execution_plan(
            config=config,
            run_spec=run,
            repo_root=config_path.parent.parent,
            config_path=config_path,
        )
    except (RepoConfigError, RunSpecParseError, PlanError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        Panel.fit(
            f"Run: [bold]{execution_plan.run_title}[/bold]\n"
            f"Repo: {execution_plan.repo_root}\n"
            f"Config: {execution_plan.config_path}\n"
            f"Spec: {execution_plan.run_spec_path}\n"
            f"Integration branch: {execution_plan.integration_branch}\n"
            f"Task PR target: {execution_plan.task_pr_target}\n"
            f"Final PR target: {execution_plan.final_pr_target}",
            title="Execution Plan",
        )
    )

    table = Table(show_header=True, header_style="bold")
    table.add_column("Task")
    table.add_column("Branch")
    table.add_column("PR Base")
    table.add_column("Depends On")
    table.add_column("Validation")
    table.add_column("Prompt")

    for task in execution_plan.tasks:
        depends_on = ", ".join(task.depends_on) if task.depends_on else "-"
        validation = ", ".join(task.validation_commands) if task.validation_commands else "-"
        table.add_row(
            f"{task.id} ({task.title})",
            task.branch_name,
            task.pr_base,
            depends_on,
            validation,
            task.prompt,
        )

    console.print(table)


@app.command("pr-plan")
def pr_plan(
    run_spec: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    repo: Path | None = typer.Option(
        None,
        "--repo",
        file_okay=False,
        dir_okay=True,
        help="Repo root to use when resolving .oats/config.toml.",
    ),
) -> None:
    """Print the Git and gh commands for task PRs into the integration branch and the final PR to main."""

    search_root = repo.resolve() if repo else run_spec.resolve().parent

    try:
        config_path = find_repo_config(search_root)
        config = load_repo_config(config_path)
        run = parse_run_spec(run_spec.resolve())
        execution_plan = build_execution_plan(
            config=config,
            run_spec=run,
            repo_root=config_path.parent.parent,
            config_path=config_path,
        )
    except (RepoConfigError, RunSpecParseError, PlanError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        Panel.fit(
            f"Integration branch: {execution_plan.integration_branch}\n"
            f"Task PR target: {execution_plan.task_pr_target}\n"
            f"Final PR target: {execution_plan.final_pr_target}\n"
            f"Auto-merge task PRs: {'yes' if config.git.auto_merge_task_prs_into_integration else 'no'}\n"
            f"Merge operator: {config.agents.merge_operator}",
            title="PR Workflow",
        )
    )

    console.print("[bold]Integration branch setup[/bold]")
    for command in build_integration_branch_commands(execution_plan):
        console.print(shlex.join(command), markup=False)

    task_prs = build_task_pr_plans(execution_plan)
    console.print("\n[bold]Task PR sequence[/bold]")
    for task_pr in task_prs:
        console.print(f"# {task_pr.task_id}")
        console.print(shlex.join(build_pr_create_command(task_pr)), markup=False)
        if config.git.auto_merge_task_prs_into_integration:
            console.print(
                f"{config.agents.merge_operator} will merge {task_pr.head_branch} into {execution_plan.integration_branch}",
                markup=False,
            )

    if config.git.auto_merge_task_prs_into_integration and config.git.auto_create_final_pr:
        final_pr = build_final_pr_plan(execution_plan)
        console.print("\n[bold]Final PR[/bold]")
        console.print(shlex.join(build_pr_create_command(final_pr)), markup=False)
    else:
        console.print("\n[bold]Final PR[/bold]")
        console.print("Skipped until task PRs are merged into the integration branch.", markup=False)


@app.command("pr-apply")
def pr_apply(
    run_spec: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    repo: Path | None = typer.Option(
        None,
        "--repo",
        file_okay=False,
        dir_okay=True,
        help="Repo root to use when resolving .oats/config.toml.",
    ),
    execute: bool = typer.Option(
        False,
        "--execute/--dry-run",
        help="Run git and gh commands instead of only recording them.",
    ),
) -> None:
    """Apply the PR workflow: create task PRs into the integration branch, merge them, then create the final PR."""

    search_root = repo.resolve() if repo else run_spec.resolve().parent

    try:
        config_path = find_repo_config(search_root)
        config = load_repo_config(config_path)
        run = parse_run_spec(run_spec.resolve())
        execution_plan = build_execution_plan(
            config=config,
            run_spec=run,
            repo_root=config_path.parent.parent,
            config_path=config_path,
        )
        apply_record = execute_pr_plan(
            execution_plan,
            config,
            execute=execute,
        )
    except (RepoConfigError, RunSpecParseError, PlanError, RuntimeError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    runs_dir = execution_plan.repo_root / ".oats" / "pr-runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    record_name = f"{execution_plan.run_spec_path.stem}-{apply_record.recorded_at.strftime('%Y%m%dT%H%M%SZ')}.json"
    record_path = runs_dir / record_name
    apply_record.record_path = record_path
    record_path.write_text(apply_record.model_dump_json(indent=2))

    console.print(
        Panel.fit(
            f"Run: [bold]{apply_record.run_title}[/bold]\n"
            f"Repo: {apply_record.repo_root}\n"
            f"Integration branch: {apply_record.integration_branch}\n"
            f"Final PR target: {apply_record.final_pr_target}\n"
            f"Auto-merge task PRs: {'yes' if apply_record.auto_merge_enabled else 'no'}\n"
            f"Final PR created: {'yes' if apply_record.final_pr_created else 'no'}\n"
            f"Mode: {'execute' if apply_record.executed else 'dry-run'}\n"
            f"Record: {apply_record.record_path}",
            title="PR Apply",
        )
    )

    table = Table(show_header=True, header_style="bold")
    table.add_column("Label")
    table.add_column("Executed")
    table.add_column("Exit")
    table.add_column("Agent")
    table.add_column("Session")
    table.add_column("Command")

    for command_record in apply_record.commands:
        table.add_row(
            command_record.label,
            "yes" if command_record.executed else "no",
            str(command_record.exit_code),
            command_record.agent or "-",
            command_record.session_id or "-",
            shlex.join(command_record.command),
        )

    console.print(table)


@app.command(
    help=(
        "Legacy compatibility command. "
        "Use `oats prefect run`."
    )
)
def run(
    run_spec: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    repo: Path | None = typer.Option(
        None,
        "--repo",
        file_okay=False,
        dir_okay=True,
        help="Repo root to use when resolving .oats/config.toml.",
    ),
    read_only: bool = typer.Option(
        True,
        "--read-only/--allow-writes",
        help="Invoke agents in non-destructive mode.",
    ),
    timeout_seconds: int = typer.Option(
        20,
        "--timeout-seconds",
        min=1,
        help="Maximum time to wait for each provider call before returning partial session metadata.",
    ),
    dangerous_bypass: bool = typer.Option(
        False,
        "--dangerous-bypass",
        help="When writes are allowed, invoke Codex/Claude with permission-bypass flags.",
    ),
    skip_planner: bool = typer.Option(
        True,
        "--skip-planner/--run-planner",
        help="Use the persisted execution plan directly instead of waiting on a separate planner agent step.",
    ),
) -> None:
    """Legacy local-runtime execution path that persists intermediary runtime state."""

    try:
        config, _, execution_plan = _load_execution_plan(run_spec, repo)
    except (RepoConfigError, RunSpecParseError, PlanError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    try:
        record, runtime_state = _execute_run(
            config=config,
            execution_plan=execution_plan,
            read_only=read_only,
            timeout_seconds=timeout_seconds,
            dangerous_bypass=dangerous_bypass,
            skip_planner=skip_planner,
        )
    except AgentInvocationError as exc:
        console.print(f"[red]Execution error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _persist_run_record_and_state(
        execution_plan=execution_plan,
        record=record,
        runtime_state=runtime_state,
    )
    _print_execution_record(record, runtime_state)


@app.command(help="Legacy compatibility command for resuming persisted local-runtime state.")
def resume(
    run_id: str | None = typer.Argument(
        None,
        help="Run id to resume. If omitted, the most recent runtime state is used.",
    ),
    state_file: Path | None = typer.Option(
        None,
        "--state-file",
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Explicit path to a .oats/runtime/<run-id>/state.json file.",
    ),
    repo: Path | None = typer.Option(
        None,
        "--repo",
        file_okay=False,
        dir_okay=True,
        help="Repo root to use when resolving .oats/config.toml.",
    ),
    read_only: bool = typer.Option(
        True,
        "--read-only/--allow-writes",
        help="Invoke agents in non-destructive mode.",
    ),
    timeout_seconds: int = typer.Option(
        20,
        "--timeout-seconds",
        min=1,
        help="Maximum time to wait for each provider call before returning partial session metadata.",
    ),
    dangerous_bypass: bool = typer.Option(
        False,
        "--dangerous-bypass",
        help="When writes are allowed, invoke Codex/Claude with permission-bypass flags.",
    ),
    retry_failed: bool = typer.Option(
        False,
        "--retry-failed",
        help="Reset failed, timed-out, or interrupted tasks back to pending before resuming.",
    ),
    refresh_pr_stack_only: bool = typer.Option(
        False,
        "--refresh-pr-stack-only",
        help="Refresh stacked PR state and unblock merge-gated tasks without invoking planner/executor agents.",
    ),
    skip_planner: bool = typer.Option(
        True,
        "--skip-planner/--run-planner",
        help="Use the persisted execution plan directly instead of waiting on a separate planner agent step.",
    ),
) -> None:
    """Resume an interrupted OATS run from its persisted runtime state."""

    search_root = repo.resolve() if repo else Path.cwd()

    try:
        config_path = find_repo_config(search_root)
        config = load_repo_config(config_path)
        runtime_state = resolve_runtime_state(
            config_path.parent.parent,
            run_id=run_id,
            state_path=state_file.resolve() if state_file else None,
        )
        if retry_failed:
            _prepare_retryable_tasks(runtime_state)
            write_runtime_state(runtime_state)
        if refresh_pr_stack_only:
            updated_state = resume_stacked_pr_run(
                run_id=str(runtime_state.run_id),
                repo_root=config_path.parent.parent,
                github_client=_GhCliClient(config_path.parent.parent),
            )
            _print_runtime_status(
                updated_state,
                state_path=updated_state.runtime_dir / "state.json",
            )
            raise typer.Exit(code=0)
        if runtime_state.status == "completed":
            console.print(
                f"[yellow]Run {runtime_state.run_id} is already completed.[/yellow]"
            )
            raise typer.Exit(code=0)
        execution_plan = build_execution_plan(
            config=config,
            run_spec=parse_run_spec(runtime_state.run_spec_path),
            repo_root=config_path.parent.parent,
            config_path=config_path,
        )
        record, updated_state = _execute_run(
            config=config,
            execution_plan=execution_plan,
            read_only=read_only,
            timeout_seconds=timeout_seconds,
            dangerous_bypass=dangerous_bypass,
            skip_planner=skip_planner,
            runtime_state=runtime_state,
        )
    except (RepoConfigError, RunSpecParseError, PlanError, FileNotFoundError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _persist_run_record_and_state(
        execution_plan=execution_plan,
        record=record,
        runtime_state=updated_state,
    )
    _print_execution_record(record, updated_state)


@app.command(help="Refresh stacked PR state for a persisted local-runtime run without executing tasks.")
def refresh(
    run_id: str | None = typer.Argument(
        None,
        help="Run id to refresh. If omitted, the most recent runtime state is used.",
    ),
    state_file: Path | None = typer.Option(
        None,
        "--state-file",
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Explicit path to a .oats/runtime/<run-id>/state.json file.",
    ),
    repo: Path | None = typer.Option(
        None,
        "--repo",
        file_okay=False,
        dir_okay=True,
        help="Repo root to use when resolving .oats/config.toml.",
    ),
) -> None:
    try:
        if state_file is not None:
            runtime_state = resolve_runtime_state(Path.cwd(), state_path=state_file.resolve())
            repo_root = runtime_state.repo_root
            state_path = state_file.resolve()
        else:
            search_root = repo.resolve() if repo else Path.cwd()
            config_path = find_repo_config(search_root)
            repo_root = config_path.parent.parent
            runtime_state = resolve_runtime_state(repo_root, run_id=run_id)
            state_path = runtime_state.runtime_dir / "state.json"
        refreshed = refresh_run(
            state=runtime_state,
            github_client=_GhCliClient(repo_root),
        )
    except (RepoConfigError, FileNotFoundError, RuntimeError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _print_runtime_status(refreshed, state_path=state_path)


@app.command(help="Legacy compatibility command for inspecting persisted local-runtime state.")
def status(
    run_id: str | None = typer.Argument(
        None,
        help="Run id to inspect. If omitted, the most recent runtime state is used.",
    ),
    state_file: Path | None = typer.Option(
        None,
        "--state-file",
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Explicit path to a .oats/runtime/<run-id>/state.json file.",
    ),
    repo: Path | None = typer.Option(
        None,
        "--repo",
        file_okay=False,
        dir_okay=True,
        help="Repo root to use when resolving .oats/config.toml.",
    ),
    stale_after_seconds: int = typer.Option(
        DEFAULT_STALE_AFTER_SECONDS,
        "--stale-after-seconds",
        min=1,
        help="Mark active runs stale when heartbeat age exceeds this threshold.",
    ),
) -> None:
    """Legacy local-runtime status for `.oats/runtime` state files."""

    try:
        if state_file is not None:
            resolved_state_path = state_file.resolve()
            runtime_state = resolve_runtime_state(Path.cwd(), state_path=resolved_state_path)
        else:
            search_root = repo.resolve() if repo else Path.cwd()
            config_path = find_repo_config(search_root)
            runtime_state = resolve_runtime_state(config_path.parent.parent, run_id=run_id)
            resolved_state_path = runtime_state.runtime_dir / "state.json"
    except (RepoConfigError, FileNotFoundError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    _print_runtime_status(
        runtime_state,
        state_path=resolved_state_path,
        stale_after_seconds=stale_after_seconds,
    )


@app.command(help="Legacy compatibility command for watching persisted local-runtime state.")
def watch(
    run_id: str | None = typer.Argument(
        None,
        help="Run id to inspect. If omitted, the most recent runtime state is used.",
    ),
    state_file: Path | None = typer.Option(
        None,
        "--state-file",
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Explicit path to a .oats/runtime/<run-id>/state.json file.",
    ),
    repo: Path | None = typer.Option(
        None,
        "--repo",
        file_okay=False,
        dir_okay=True,
        help="Repo root to use when resolving .oats/config.toml.",
    ),
    interval_seconds: float = typer.Option(
        5.0,
        "--interval-seconds",
        min=0.0,
        help="Polling interval between runtime state refreshes.",
    ),
    iterations: int | None = typer.Option(
        None,
        "--iterations",
        min=1,
        help="Maximum number of snapshots to print before exiting.",
    ),
    stale_after_seconds: int = typer.Option(
        DEFAULT_STALE_AFTER_SECONDS,
        "--stale-after-seconds",
        min=1,
        help="Mark active runs stale when heartbeat age exceeds this threshold.",
    ),
) -> None:
    """Continuously print runtime status snapshots while a run is active."""

    try:
        if state_file is not None:
            resolved_state_path = state_file.resolve()
        else:
            search_root = repo.resolve() if repo else Path.cwd()
            config_path = find_repo_config(search_root)
            runtime_state = resolve_runtime_state(config_path.parent.parent, run_id=run_id)
            resolved_state_path = runtime_state.runtime_dir / "state.json"
    except (RepoConfigError, FileNotFoundError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    snapshots_printed = 0
    last_snapshot: str | None = None
    while True:
        try:
            runtime_state = resolve_runtime_state(Path.cwd(), state_path=resolved_state_path)
        except FileNotFoundError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1) from exc

        snapshot = _build_runtime_status_text(
            runtime_state,
            state_path=resolved_state_path,
            stale_after_seconds=stale_after_seconds,
        )
        if snapshot != last_snapshot:
            console.print(Panel.fit(snapshot, title="Runtime Status"))
            last_snapshot = snapshot
            snapshots_printed += 1

        if iterations is not None and snapshots_printed >= iterations:
            break
        if runtime_state.finished_at is not None or runtime_state.status in {
            "completed",
            "failed",
            "timed_out",
        }:
            break
        time.sleep(interval_seconds)


@prefect_app.command("deploy")
def prefect_deploy(
    run_spec: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    repo: Path | None = typer.Option(
        None,
        "--repo",
        file_okay=False,
        dir_okay=True,
        help="Repo root to use when resolving .oats/config.toml.",
    ),
) -> None:
    """Register or update a Prefect deployment from a Markdown run spec."""

    try:
        run_definition = load_run_definition(run_spec, repo_root=repo)
        repo_config, _ = _load_repo_config_for_run_spec(run_spec, repo)
        registered = deploy_run_spec(run_definition, repo_config)
    except (
        PrefectApiError,
        RepoConfigError,
        RunSpecParseError,
        UnsupportedRunDefinitionInputError,
    ) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    action = "Created" if registered.created else "Updated"
    console.print(
        Panel.fit(
            f"{action} deployment [bold]{registered.deployment_name}[/bold]\n"
            f"Deployment ID: {registered.deployment_id}\n"
            f"Flow: {registered.flow_name}",
            title="Prefect Deployment",
        )
    )


@prefect_app.command("run")
def prefect_run(
    run_spec: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    repo: Path | None = typer.Option(
        None,
        "--repo",
        file_okay=False,
        dir_okay=True,
        help="Repo root to use when resolving .oats/config.toml.",
    ),
) -> None:
    """Create a manual Prefect flow run from a Markdown run spec."""

    try:
        run_definition = load_run_definition(run_spec, repo_root=repo)
        repo_config, _ = _load_repo_config_for_run_spec(run_spec, repo)
        flow_run = trigger_run_spec(run_definition, repo_config)
    except (
        PrefectApiError,
        RepoConfigError,
        RunSpecParseError,
        UnsupportedRunDefinitionInputError,
    ) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        Panel.fit(
            f"Flow run ID: [bold]{flow_run.flow_run_id}[/bold]\n"
            f"Deployment ID: {flow_run.deployment_id}\n"
            f"State: {flow_run.state_name or flow_run.state_type or '-'}",
            title="Prefect Flow Run",
        )
    )


@prefect_app.command("status")
def prefect_status(
    flow_run_id: str = typer.Argument(..., help="Prefect flow-run id to inspect."),
) -> None:
    """Print the latest Prefect status for a flow run."""

    try:
        status = read_flow_run_status(flow_run_id)
    except PrefectApiError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        Panel.fit(
            f"Flow run ID: [bold]{status.flow_run_id}[/bold]\n"
            f"Name: {status.flow_run_name or '-'}\n"
            f"State: {status.state_name or status.state_type or '-'}",
            title="Prefect Status",
        )
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
