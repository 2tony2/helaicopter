"""Application-layer shaping for OATS local-runtime records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import cast
from urllib.parse import quote

from pydantic import ConfigDict, InstanceOf, validate_call

from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.application.conversations import _resolve_conversation_identity
from helaicopter_api.ports.orchestration import StoredOatsRunRecord, StoredOatsRuntimeState
from helaicopter_api.schema.orchestration import (
    OrchestrationFactsResponse,
    OrchestrationDagEdgeResponse,
    OrchestrationDagNodeResponse,
    OrchestrationDagResponse,
    OrchestrationDagStatsResponse,
    OrchestrationInvocationResponse,
    OrchestrationRunFactResponse,
    OrchestrationRunResponse,
    OrchestrationTaskAttemptFactResponse,
    OrchestrationTaskResponse,
)
from helaicopter_api.pure.orchestration_analytics import (
    StoredRuntimeArtifact,
    StoredTerminalArtifact,
    build_oats_orchestration_facts,
)
from helaicopter_domain.ids import RunId
from helaicopter_domain.paths import EncodedProjectKey
from helaicopter_domain.vocab import ProviderName, RunRuntimeStatus, TaskRuntimeStatus
from oats.models import (
    AgentInvocationResult,
    InvocationRuntimeRecord,
    RunRuntimeState,
    RunExecutionRecord,
    TaskExecutionRecord,
    TaskRuntimeRecord,
)
from oats.prefect.analytics import StoredLocalFlowRunArtifacts, load_local_flow_run_artifacts

ACTIVE_RUN_STATUSES: set[RunRuntimeStatus] = {"pending", "planning", "running"}
STALE_RUNTIME_AFTER_SECONDS = 300
_PREFECT_ACTIVE_STATES = {"RUNNING"}
_PREFECT_PENDING_STATES = {"PENDING", "SCHEDULED", "LATE"}
_PREFECT_FAILED_STATES = {"FAILED", "CRASHED", "CANCELLED", "CANCELED", "CANCELLING"}
_SAMPLE_RUN_SPEC_NAMES = {"sample_run.md"}


@dataclass(frozen=True, slots=True)
class _ShapedRun:
    response: OrchestrationRunResponse
    last_updated_at: datetime

    @property
    def is_running(self) -> bool:
        return self.response.is_running


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def list_oats_runs(services: InstanceOf[BackendServices]) -> list[OrchestrationRunResponse]:
    """Return persisted OATS orchestration runs from the authoritative facts tables."""
    return _list_persisted_oats_runs(services)


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def get_oats_facts(services: InstanceOf[BackendServices]) -> OrchestrationFactsResponse:
    facts = build_oats_orchestration_facts(
        [
            StoredRuntimeArtifact(path=item.path, state=item.state)
            for item in services.oats_run_store.list_runtime_states()
        ],
        [
            StoredTerminalArtifact(path=item.path, record=item.record)
            for item in services.oats_run_store.list_run_records()
        ],
    )
    return OrchestrationFactsResponse(
        canonical_rules=list(facts.canonical_rules),
        run_facts=[OrchestrationRunFactResponse.model_validate(fact.to_dict()) for fact in facts.run_facts],
        task_attempt_facts=[
            OrchestrationTaskAttemptFactResponse.model_validate(fact.to_dict())
            for fact in facts.task_attempt_facts
        ],
    )


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


def _list_persisted_oats_runs(services: BackendServices) -> list[OrchestrationRunResponse]:
    settings = getattr(services, "settings", None)
    if settings is None or not settings.app_sqlite_path.exists():
        return []

    connection = _connect_readonly_sqlite(settings.app_sqlite_path)
    if connection is None:
        return []
    try:
        if not _table_exists(connection, "fact_orchestration_runs"):
            return []
        run_rows = connection.execute(
            """
            SELECT
              run_fact_id,
              run_source,
              run_id,
              flow_run_name,
              run_title,
              source_path,
              repo_root,
              config_path,
              artifact_root,
              status,
              canonical_status_source,
              has_runtime_snapshot,
              has_terminal_record,
              task_count,
              completed_task_count,
              running_task_count,
              failed_task_count,
              task_attempt_count,
              started_at,
              updated_at,
              finished_at
            FROM fact_orchestration_runs
            ORDER BY datetime(updated_at) DESC, run_id DESC
            """
        ).fetchall()
        if not run_rows:
            return []

        attempt_rows = connection.execute(
            """
            SELECT
              task_attempt_fact_id,
              run_fact_id,
              run_source,
              run_id,
              task_id,
              task_title,
              attempt,
              status,
              upstream_task_ids_json,
              agent,
              session_id,
              model,
              reasoning_effort,
              error,
              output_text,
              started_at,
              updated_at,
              finished_at,
              last_heartbeat_at,
              last_progress_event_at
            FROM fact_orchestration_task_attempts
            ORDER BY task_id ASC, attempt DESC, datetime(updated_at) DESC
            """
        ).fetchall()
    finally:
        connection.close()

    attempts_by_run: dict[str, list[sqlite3.Row]] = {}
    for row in attempt_rows:
        attempts_by_run.setdefault(str(row["run_fact_id"]), []).append(row)

    prefect_by_run_id = _prefect_flow_runs_by_id(services)
    prefect_artifacts_by_run_id = load_local_flow_run_artifacts(settings.project_root)
    responses: list[OrchestrationRunResponse] = []
    for row in run_rows:
        if _should_exclude_persisted_run(row):
            continue
        response = _shape_persisted_run(
            row,
            attempts_by_run.get(str(row["run_fact_id"]), []),
            prefect_by_run_id.get(str(row["run_id"])),
            prefect_artifacts_by_run_id.get(str(row["run_id"])),
            services=services,
        )
        responses.append(response)

    return responses


def _connect_readonly_sqlite(path: Path) -> sqlite3.Connection | None:
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    connection.row_factory = sqlite3.Row
    return connection


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _prefect_flow_runs_by_id(services: BackendServices) -> dict[str, object]:
    prefect_client = getattr(services, "prefect_client", None)
    if prefect_client is None or not hasattr(prefect_client, "list_flow_runs"):
        return {}
    try:
        flow_runs = prefect_client.list_flow_runs()
    except Exception:
        return {}
    return {str(item.flow_run_id): item for item in flow_runs}


def _should_exclude_persisted_run(row: sqlite3.Row) -> bool:
    source_path = row["source_path"]
    if source_path is None:
        return False
    return Path(str(source_path)).name in _SAMPLE_RUN_SPEC_NAMES


def _shape_persisted_run(
    row: sqlite3.Row,
    attempts: list[sqlite3.Row],
    prefect_flow_run: object | None,
    prefect_artifacts: StoredLocalFlowRunArtifacts | None,
    *,
    services: BackendServices,
) -> OrchestrationRunResponse:
    repo_root = (
        prefect_artifacts.metadata.repo_root
        if prefect_artifacts is not None
        else Path(str(row["repo_root"]))
    )
    run_status = _normalize_persisted_run_status(row, prefect_flow_run)
    tasks = _shape_persisted_tasks(
        attempts,
        repo_root=repo_root,
        run_status=run_status,
        prefect_artifacts=prefect_artifacts,
        services=services,
    )
    active_task_id = next((task.task_id for task in tasks if task.status == "running"), None)
    latest_heartbeat_at = max(
        (
            timestamp
            for timestamp in (_parse_datetime_value(task["last_heartbeat_at"]) for task in attempts)
            if timestamp is not None
        ),
        default=None,
    )
    last_updated_at = _parse_datetime_value(row["updated_at"]) or datetime.now(UTC)
    created_at = _parse_datetime_value(row["started_at"]) or last_updated_at
    finished_at = _parse_datetime_value(row["finished_at"])
    contract_version = "oats-runtime-v1" if bool(row["has_runtime_snapshot"]) else "oats-run-v1"
    source_path = str(row["source_path"] or "")
    config_path = str(row["config_path"] or "")

    return OrchestrationRunResponse(
        source="overnight-oats",
        contract_version=contract_version,
        run_id=str(row["run_id"]),
        run_title=str(row["run_title"]),
        repo_root=str(repo_root),
        config_path=config_path,
        run_spec_path=source_path,
        mode="prefect" if str(row["run_source"]) == "prefect_local" else "persisted",
        integration_branch="",
        task_pr_target="",
        final_pr_target="",
        status=run_status,
        active_task_id=active_task_id,
        heartbeat_at=_isoformat(latest_heartbeat_at),
        finished_at=_isoformat(finished_at),
        planner=None,
        tasks=tasks,
        created_at=_isoformat(created_at) or "",
        last_updated_at=_isoformat(last_updated_at) or "",
        is_running=run_status in ACTIVE_RUN_STATUSES and active_task_id is not None,
        recorded_at=_isoformat(last_updated_at) or "",
        record_path=str(row["run_fact_id"]),
        dag=_build_orchestration_dag(
            None,
            tasks,
            run_title=str(row["run_title"]),
            run_status=run_status,
            active_task_id=active_task_id,
        ),
    )


def _shape_persisted_tasks(
    attempts: list[sqlite3.Row],
    *,
    repo_root: Path,
    run_status: RunRuntimeStatus,
    prefect_artifacts: StoredLocalFlowRunArtifacts | None,
    services: BackendServices,
) -> list[OrchestrationTaskResponse]:
    latest_attempts: dict[str, sqlite3.Row] = {}
    for row in attempts:
        task_id = str(row["task_id"])
        if task_id not in latest_attempts:
            latest_attempts[task_id] = row

    prefect_attempts = _prefect_attempts_by_task_id(prefect_artifacts)

    tasks: list[OrchestrationTaskResponse] = []
    for task_id in sorted(latest_attempts):
        row = latest_attempts[task_id]
        tasks.append(
            OrchestrationTaskResponse(
                task_id=task_id,
                title=str(row["task_title"]),
                depends_on=_parse_upstream_ids(row["upstream_task_ids_json"]),
                status=_normalize_persisted_task_status(str(row["status"]), run_status),
                attempts=int(row["attempt"] or 0),
                invocation=_shape_persisted_invocation(
                    row,
                    repo_root=repo_root,
                    prefect_attempt=prefect_attempts.get(task_id),
                    services=services,
                ),
            )
        )
    return tasks


def _shape_persisted_invocation(
    row: sqlite3.Row,
    *,
    repo_root: Path,
    prefect_attempt: object | None = None,
    services: BackendServices,
) -> OrchestrationInvocationResponse | None:
    agent_value = row["agent"]
    session_id = str(row["session_id"]) if row["session_id"] is not None else None
    output_text = str(row["output_text"] or "")
    error_text = str(row["error"] or "")
    if prefect_attempt is not None:
        result = getattr(prefect_attempt, "result", None)
        if agent_value is None and isinstance(result, dict):
            agent_value = result.get("agent")
        if session_id is None:
            checkpoint_session_id = getattr(prefect_attempt, "session_id", None)
            requested_session_id = getattr(prefect_attempt, "requested_session_id", None)
            if isinstance(checkpoint_session_id, str) and checkpoint_session_id:
                session_id = checkpoint_session_id
            elif isinstance(result, dict) and isinstance(result.get("session_id"), str):
                session_id = str(result["session_id"])
            elif isinstance(requested_session_id, str) and requested_session_id:
                session_id = requested_session_id
        if not output_text and isinstance(result, dict) and isinstance(result.get("output_text"), str):
            output_text = str(result["output_text"])
        if not error_text and getattr(prefect_attempt, "error", None):
            error_text = str(getattr(prefect_attempt, "error"))
    if agent_value not in {"claude", "codex"}:
        return None
    agent = cast(ProviderName, str(agent_value))
    project_path = _normalize_repo_project_path(str(repo_root), agent) if session_id else None
    conversation_path = _canonical_conversation_path(services, provider=agent, session_id=session_id)
    task_status = str(row["status"]).strip().lower()
    return OrchestrationInvocationResponse(
        agent=agent,
        role="executor",
        command=[],
        cwd=str(repo_root),
        prompt="",
        session_id=session_id,
        output_text=output_text,
        raw_stdout="",
        raw_stderr=error_text,
        exit_code=None,
        timed_out=task_status == "timed_out",
        started_at=_isoformat(_parse_datetime_value(row["started_at"])) or "",
        last_heartbeat_at=_isoformat(_parse_datetime_value(row["last_heartbeat_at"])),
        finished_at=_isoformat(_parse_datetime_value(row["finished_at"])),
        project_path=project_path,
        conversation_path=conversation_path,
    )


def _parse_upstream_ids(raw: object) -> list[str]:
    if raw is None:
        return []
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if isinstance(item, str)]


def _prefect_attempts_by_task_id(
    prefect_artifacts: StoredLocalFlowRunArtifacts | None,
) -> dict[str, object]:
    if prefect_artifacts is None:
        return {}
    attempts_by_task_id: dict[str, object] = {}
    for checkpoint in prefect_artifacts.attempts:
        task_id = checkpoint.task_id
        if task_id not in attempts_by_task_id:
            attempts_by_task_id[task_id] = checkpoint
    return attempts_by_task_id


def _normalize_persisted_run_status(row: sqlite3.Row, prefect_flow_run: object | None) -> RunRuntimeStatus:
    prefect_status = _normalize_prefect_flow_run_status(prefect_flow_run)
    if prefect_status is not None:
        return prefect_status
    status = str(row["status"]).strip().lower()
    updated_at = _parse_datetime_value(row["updated_at"])
    if status in ACTIVE_RUN_STATUSES and updated_at is not None:
        if (datetime.now(UTC) - updated_at).total_seconds() > STALE_RUNTIME_AFTER_SECONDS:
            return "pending"
    if status == "completed":
        return "completed"
    if status in {"failed", "timed_out"}:
        return cast(RunRuntimeStatus, status)
    if status in {"planning", "pending", "running"}:
        return cast(RunRuntimeStatus, status)
    if status in {"succeeded", "success"}:
        return "completed"
    return "pending"


def _normalize_prefect_flow_run_status(prefect_flow_run: object | None) -> RunRuntimeStatus | None:
    if prefect_flow_run is None:
        return None
    state_type = str(getattr(prefect_flow_run, "state_type", "") or "").upper()
    if state_type in _PREFECT_ACTIVE_STATES:
        return "running"
    if state_type in _PREFECT_PENDING_STATES:
        return "pending"
    if state_type == "COMPLETED":
        return "completed"
    if state_type in _PREFECT_FAILED_STATES:
        return "failed"
    return None


def _normalize_persisted_task_status(status: str, run_status: RunRuntimeStatus) -> TaskRuntimeStatus:
    normalized = status.strip().lower()
    if normalized == "running" and run_status == "completed":
        return "succeeded"
    if normalized == "running" and run_status == "pending":
        return "pending"
    if normalized in {"pending", "blocked"} and run_status == "completed":
        return "skipped"
    if normalized in {"pending", "running", "succeeded", "failed", "timed_out", "skipped", "blocked"}:
        return cast(TaskRuntimeStatus, normalized)
    if normalized in {"completed", "success"}:
        return "succeeded"
    return "pending"


def _shape_runtime_state(
    stored: StoredOatsRuntimeState,
    *,
    services: BackendServices | None = None,
) -> _ShapedRun:
    state = stored.state
    repo_root = state.repo_root
    is_stale = _is_stale_runtime_state(state)
    heartbeat_at = _isoformat(state.heartbeat_at)
    planner = _shape_invocation(state.planner, repo_root, services=services)
    tasks = [_shape_runtime_task(task, repo_root, stale=is_stale, services=services) for task in state.tasks]
    last_updated_at = _coerce_datetime(state.updated_at)
    status = _reconcile_runtime_run_status(state, tasks, stale=is_stale)
    active_task_id = None if is_stale else state.active_task_id
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
        status=status,
        active_task_id=active_task_id,
        heartbeat_at=heartbeat_at,
        finished_at=_isoformat(state.finished_at),
        planner=planner,
        tasks=tasks,
        created_at=_isoformat(state.started_at) or heartbeat_at or "",
        last_updated_at=_isoformat(last_updated_at) or "",
        is_running=not is_stale and state.status in ACTIVE_RUN_STATUSES and state.finished_at is None,
        recorded_at=_isoformat(state.updated_at) or heartbeat_at or "",
        record_path=str(stored.path),
        dag=_build_orchestration_dag(
            planner,
            tasks,
            run_title=state.run_title,
            run_status=status,
            active_task_id=active_task_id,
        ),
    )
    return _ShapedRun(response=response, last_updated_at=last_updated_at)


def _shape_run_record(
    stored: StoredOatsRunRecord,
    *,
    services: BackendServices | None = None,
) -> _ShapedRun:
    record = stored.record
    repo_root = record.repo_root
    planner = _shape_invocation(record.planner, repo_root, services=services)
    tasks = [_shape_record_task(task, repo_root, services=services) for task in record.tasks]
    recorded_at = _coerce_datetime(record.recorded_at)
    status = _derive_run_status(record)
    response = OrchestrationRunResponse(
        source="overnight-oats",
        contract_version="oats-run-v1",
        run_id=record.run_id or RunId(stored.path.stem),
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
        ),
    )
    return _ShapedRun(response=response, last_updated_at=recorded_at)


def _shape_runtime_task(
    task: TaskRuntimeRecord,
    repo_root: Path,
    *,
    stale: bool = False,
    services: BackendServices | None = None,
) -> OrchestrationTaskResponse:
    invocation = _shape_invocation(
        task.invocation,
        repo_root,
        fallback_agent=task.agent,
        fallback_role=task.role,
        services=services,
    )
    status: TaskRuntimeStatus = "pending" if stale and task.status == "running" else task.status
    return OrchestrationTaskResponse(
        task_id=task.task_id,
        title=task.title,
        depends_on=list(task.depends_on),
        status=status,
        attempts=task.attempts,
        invocation=invocation,
    )


def _shape_record_task(
    task: TaskExecutionRecord,
    repo_root: Path,
    *,
    services: BackendServices | None = None,
) -> OrchestrationTaskResponse:
    invocation = _shape_invocation(task.invocation, repo_root, services=services)
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
    fallback_agent: ProviderName | None = None,
    fallback_role: str | None = None,
    services: BackendServices | None = None,
) -> OrchestrationInvocationResponse | None:
    if invocation is None:
        if fallback_agent is None or fallback_role is None:
            return None
        session_id = None
        agent: ProviderName = fallback_agent
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
        last_heartbeat_at = None
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
        last_heartbeat_at = _isoformat(getattr(invocation, "last_heartbeat_at", None))
        finished_at = _isoformat(invocation.finished_at)

    project_path = _normalize_repo_project_path(str(repo_root), agent) if session_id else None
    conversation_path = _canonical_conversation_path(services, provider=agent, session_id=session_id)
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
        last_heartbeat_at=last_heartbeat_at,
        finished_at=finished_at,
        project_path=project_path,
        conversation_path=conversation_path,
    )


def _canonical_conversation_path(
    services: BackendServices | None,
    *,
    provider: ProviderName,
    session_id: str | None,
) -> str | None:
    if services is None or not session_id:
        return None
    try:
        resolved = _resolve_conversation_identity(services, provider=provider, session_id=session_id)
    except AttributeError:
        return None
    if resolved is None:
        return None
    return f"/conversations/by-ref/{quote(resolved.conversation_ref, safe='')}"


def _normalize_repo_project_path(repo_root: str, agent: ProviderName) -> EncodedProjectKey:
    encoded = repo_root.replace("/", "-")
    if agent == "codex":
        return f"codex:{encoded}"
    return encoded


def _derive_task_status(invocation: AgentInvocationResult) -> TaskRuntimeStatus:
    if invocation.timed_out:
        return "timed_out"
    if invocation.exit_code == 0:
        return "succeeded"
    return "failed"


def _derive_run_status(record: RunExecutionRecord) -> RunRuntimeStatus:
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
    run_status: RunRuntimeStatus,
    active_task_id: str | None,
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
            status=_derive_invocation_status(planner, run_status=run_status, is_planner=True),
            is_active=run_status == "planning" and planner.finished_at is None,
            last_heartbeat_at=planner.last_heartbeat_at,
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
            agent=invocation.agent if invocation is not None else cast(ProviderName, "claude"),
            session_id=invocation.session_id if invocation is not None else None,
            project_path=invocation.project_path if invocation is not None else None,
            conversation_path=invocation.conversation_path if invocation is not None else None,
            status=task.status,
            is_active=active_task_id == task.task_id or task.status == "running",
            attempts=task.attempts,
            last_heartbeat_at=invocation.last_heartbeat_at if invocation is not None else None,
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
    provider_breakdown: dict[ProviderName, int] = {}
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


def _parse_datetime_value(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _coerce_datetime(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _coerce_datetime(parsed)


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _coerce_datetime(value).isoformat().replace("+00:00", "Z")


def _is_stale_runtime_state(state: RunRuntimeState, *, now: datetime | None = None) -> bool:
    if state.finished_at is not None or state.status not in ACTIVE_RUN_STATUSES:
        return False
    if state.active_task_id is None and not any(task.status == "running" for task in state.tasks):
        return False
    reference_time = now or datetime.now(UTC)
    heartbeat_age = (reference_time - _coerce_datetime(state.heartbeat_at)).total_seconds()
    return heartbeat_age > STALE_RUNTIME_AFTER_SECONDS


def _reconcile_runtime_run_status(
    state: RunRuntimeState,
    tasks: list[OrchestrationTaskResponse],
    *,
    stale: bool,
) -> RunRuntimeStatus:
    if not stale:
        return state.status
    if any(task.status in {"pending", "blocked"} for task in tasks):
        return "pending"
    if any(task.status == "timed_out" for task in tasks):
        return "timed_out"
    if any(task.status == "failed" for task in tasks):
        return "failed"
    return "completed"


def _derive_invocation_status(
    invocation: OrchestrationInvocationResponse,
    *,
    run_status: RunRuntimeStatus,
    is_planner: bool = False,
) -> TaskRuntimeStatus | RunRuntimeStatus:
    if invocation.timed_out:
        return "timed_out"
    if invocation.exit_code == 0 and invocation.finished_at:
        return "succeeded"
    if invocation.exit_code not in (None, 0):
        return "failed"
    if is_planner and run_status == "planning":
        return "running"
    return "pending"
