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

from helaicopter_api.application.conversation_refs import build_conversation_ref
from helaicopter_api.application.runtime_materialization import (
    get_materialized_runtime_run,
    project_operator_actions,
)
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.application.conversations import _resolve_conversation_identity
from helaicopter_api.ports.orchestration import StoredOatsRunRecord, StoredOatsRuntimeState
from helaicopter_api.schema.orchestration import (
    OrchestrationFactsResponse,
    OrchestrationDagEdgeResponse,
    OrchestrationDagNodeResponse,
    OrchestrationDagResponse,
    OrchestrationDagStatsResponse,
    OrchestrationFeatureBranchResponse,
    OrchestrationFinalPullRequestResponse,
    OrchestrationGraphMutationResponse,
    OrchestrationGraphNodeResponse,
    OrchestrationInsertTaskRequest,
    OrchestrationOperatorActionResponse,
    OrchestrationRunActionResponse,
    OrchestrationRerouteTaskRequest,
    OrchestrationInvocationResponse,
    OrchestrationOperationHistoryResponse,
    OrchestrationReviewSummaryResponse,
    OrchestrationRunFactResponse,
    OrchestrationRunResponse,
    OrchestrationTaskPullRequestResponse,
    OrchestrationTaskAttemptFactResponse,
    OrchestrationTaskResponse,
    OrchestrationTypedEdgeResponse,
)
from helaicopter_api.schema.runtime_materialization import (
    MaterializedGraphMutation,
    MaterializedRuntimeRun,
    MaterializedTaskAttempt,
)
from helaicopter_api.pure.orchestration_analytics import (
    StoredRuntimeArtifact,
    StoredTerminalArtifact,
    build_oats_orchestration_facts,
)
from helaicopter_domain.ids import RunId
from helaicopter_domain.paths import EncodedProjectKey
from helaicopter_domain.vocab import ProviderName, RunRuntimeStatus, TaskRuntimeStatus
from oats.graph import EdgePredicate, GraphMutation, TaskKind, TaskNode, TypedEdge
from oats.models import (
    AgentInvocationResult,
    InvocationRuntimeRecord,
    RunRuntimeState,
    RunExecutionRecord,
    TaskExecutionRecord,
    TaskRuntimeRecord,
)
from oats.identity import generate_discovered_task_id, generate_mutation_id
from oats.runtime_state import write_runtime_state

ACTIVE_RUN_STATUSES: set[RunRuntimeStatus] = {"pending", "planning", "running"}
STALE_RUNTIME_AFTER_SECONDS = 300
_SAMPLE_RUN_SPEC_NAMES = {"sample_run.md"}


@dataclass(frozen=True, slots=True)
class _ShapedRun:
    response: OrchestrationRunResponse
    last_updated_at: datetime

    @property
    def is_running(self) -> bool:
        return self.response.is_running


@dataclass(slots=True)
class _ConversationPathLookup:
    services: BackendServices | None
    paths_by_identity: dict[tuple[ProviderName, str], str | None]

    def resolve(self, *, provider: ProviderName, session_id: str | None) -> str | None:
        if not session_id:
            return None
        key = (provider, session_id)
        if key in self.paths_by_identity:
            return self.paths_by_identity[key]
        if self.services is None:
            self.paths_by_identity[key] = None
            return None
        try:
            resolved = _resolve_conversation_identity(self.services, provider=provider, session_id=session_id)
        except AttributeError:
            path = None
        else:
            path = _conversation_path_from_ref(resolved.conversation_ref) if resolved is not None else None
        self.paths_by_identity[key] = path
        return path


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def list_oats_runs(services: InstanceOf[BackendServices]) -> list[OrchestrationRunResponse]:
    """Return persisted OATS orchestration runs from the authoritative facts tables.

    Merges shaped run records, runtime state snapshots, and SQLite fact rows,
    deduplicating by run ID and preferring the most recently updated
    representation. Results are sorted newest-first.

    Args:
        services: Initialised backend services providing the OATS run store
            and optional backend services.

    Returns:
        List of ``OrchestrationRunResponse`` objects sorted by last-updated
        timestamp descending.
    """
    runs_by_id: dict[str, _ShapedRun] = {}

    for stored in services.oats_run_store.list_run_records():
        _merge_run(runs_by_id, _shape_run_record(stored))
    for stored in services.oats_run_store.list_runtime_states():
        _merge_run(runs_by_id, _shape_runtime_state(stored))
    for response in _list_persisted_oats_runs(services):
        _merge_run(
            runs_by_id,
            _ShapedRun(
                response=response,
                last_updated_at=_parse_datetime_value(response.last_updated_at) or datetime.now(UTC),
            ),
        )

    return [
        shaped.response
        for shaped in sorted(runs_by_id.values(), key=lambda item: item.last_updated_at, reverse=True)
    ]


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def get_oats_facts(services: InstanceOf[BackendServices]) -> OrchestrationFactsResponse:
    """Return aggregated orchestration analytics facts for all OATS runs.

    Builds canonical run and task-attempt fact tables from the in-memory
    runtime state snapshots and terminal run records held by the OATS run
    store.

    Args:
        services: Initialised backend services providing the OATS run store.

    Returns:
        An ``OrchestrationFactsResponse`` containing canonical rules, per-run
        facts, and per-task-attempt facts derived from all available artifacts.
    """
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


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def get_oats_run(
    services: InstanceOf[BackendServices],
    run_id: str,
) -> OrchestrationRunResponse:
    stored = _get_runtime_state_for_run(services, run_id)
    materialized = get_materialized_runtime_run(services, run_id)
    return _shape_runtime_state(stored, services=services, materialized=materialized).response


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def pause_oats_run(
    services: InstanceOf[BackendServices],
    run_id: str,
) -> OrchestrationRunActionResponse:
    stored = _get_runtime_state_for_run(services, run_id)
    state = stored.state
    state.status = "paused"
    state.active_task_id = None
    state.graph_mutations.append(
        GraphMutation(
            mutation_id=generate_mutation_id(),
            kind="pause_run",
            discovered_by="operator",
            source="operator",
        )
    )
    write_runtime_state(state)
    return _shape_runtime_action_response(state)


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def cancel_oats_task(
    services: InstanceOf[BackendServices],
    run_id: str,
    task_id: str,
) -> OrchestrationRunActionResponse:
    stored = _get_runtime_state_for_run(services, run_id)
    state = stored.state
    graph = _require_graph(state, run_id)
    graph.cancel_task(task_id)
    _sync_state_tasks_from_graph(state)
    state.graph_mutations.append(
        GraphMutation(
            mutation_id=generate_mutation_id(),
            kind="cancel_task",
            discovered_by="operator",
            source="operator",
            nodes_added=[task_id],
        )
    )
    write_runtime_state(state)
    return _shape_runtime_action_response(state)


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def force_retry_oats_task(
    services: InstanceOf[BackendServices],
    run_id: str,
    task_id: str,
) -> OrchestrationRunActionResponse:
    stored = _get_runtime_state_for_run(services, run_id)
    state = stored.state
    graph = _require_graph(state, run_id)
    graph.force_retry_task(task_id)
    _sync_state_tasks_from_graph(state)
    state.graph_mutations.append(
        GraphMutation(
            mutation_id=generate_mutation_id(),
            kind="force_retry_task",
            discovered_by="operator",
            source="operator",
            nodes_added=[task_id],
        )
    )
    write_runtime_state(state)
    return _shape_runtime_action_response(state)


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def reroute_oats_task(
    services: InstanceOf[BackendServices],
    run_id: str,
    task_id: str,
    request: OrchestrationRerouteTaskRequest,
) -> OrchestrationRunActionResponse:
    stored = _get_runtime_state_for_run(services, run_id)
    state = stored.state
    graph = _require_graph(state, run_id)
    graph.reroute_task(task_id, provider=request.provider, model=request.model)
    _sync_state_tasks_from_graph(state)
    state.graph_mutations.append(
        GraphMutation(
            mutation_id=generate_mutation_id(),
            kind="reroute_task",
            discovered_by="operator",
            source="operator",
            nodes_added=[task_id],
        )
    )
    write_runtime_state(state)
    return _shape_runtime_action_response(state)


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def insert_oats_task(
    services: InstanceOf[BackendServices],
    run_id: str,
    request: OrchestrationInsertTaskRequest,
) -> OrchestrationRunActionResponse:
    stored = _get_runtime_state_for_run(services, run_id)
    state = stored.state
    graph = _require_graph(state, run_id)
    task_id = generate_discovered_task_id()
    graph.add_node(
        TaskNode(
            task_id=task_id,
            kind=TaskKind(request.kind),
            title=request.title,
            agent=request.agent,
            model=request.model,
            discovered_by="operator",
        )
    )
    inserted_edges: list[TypedEdge] = []
    depends_on: list[str] = []
    for dependency in request.dependencies:
        edge = TypedEdge(
            from_task=dependency.task_id,
            to_task=task_id,
            predicate=EdgePredicate(dependency.predicate),
        )
        graph.add_edge(edge)
        inserted_edges.append(edge)
        depends_on.append(str(dependency.task_id))
    state.tasks.append(
        TaskRuntimeRecord(
            task_id=task_id,
            title=request.title,
            depends_on=depends_on,
            branch_name=f"oats/task/{task_id}",
            pr_base=state.integration_branch,
            agent=request.agent,
            status="pending",
            discovered_by="operator",
        )
    )
    _sync_state_tasks_from_graph(state)
    state.graph_mutations.append(
        GraphMutation(
            mutation_id=generate_mutation_id(),
            kind="insert_tasks",
            discovered_by="operator",
            source="operator",
            nodes_added=[task_id],
            edges_added=inserted_edges,
        )
    )
    write_runtime_state(state)
    return _shape_runtime_action_response(state, task_id=task_id)


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


def _get_runtime_state_for_run(
    services: BackendServices,
    run_id: str,
) -> StoredOatsRuntimeState:
    for stored in services.oats_run_store.list_runtime_states():
        if stored.state.run_id == run_id:
            return stored
    raise ValueError(f"OATS runtime state not found for run '{run_id}'")


def _require_graph(state: RunRuntimeState, run_id: str):
    if state.graph is None:
        raise ValueError(f"OATS run '{run_id}' does not have a graph-native runtime state")
    return state.graph


def _sync_state_tasks_from_graph(state: RunRuntimeState) -> None:
    if state.graph is None:
        return
    tasks_by_id = {task.task_id: task for task in state.tasks}
    for task_id, node in state.graph.nodes.items():
        task = tasks_by_id.get(task_id)
        if task is None:
            continue
        task.status = node.status
        if node.agent in {"claude", "codex", "openclaw", "opencloud"}:
            task.agent = cast(ProviderName, node.agent)


def _shape_runtime_action_response(
    state: RunRuntimeState,
    *,
    task_id: str | None = None,
) -> OrchestrationRunActionResponse:
    shaped = _shape_runtime_state(
        StoredOatsRuntimeState(path=state.runtime_dir / "state.json", state=state)
    ).response
    return OrchestrationRunActionResponse(**shaped.model_dump(), task_id=task_id)


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

    conversation_paths = _build_conversation_path_lookup(services)
    responses: list[OrchestrationRunResponse] = []
    for row in run_rows:
        if _should_exclude_persisted_run(row):
            continue
        response = _shape_persisted_run(
            row,
            attempts_by_run.get(str(row["run_fact_id"]), []),
            conversation_paths=conversation_paths,
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


def _should_exclude_persisted_run(row: sqlite3.Row) -> bool:
    source_path = row["source_path"]
    if source_path is None:
        return False
    return Path(str(source_path)).name in _SAMPLE_RUN_SPEC_NAMES


def _shape_persisted_run(
    row: sqlite3.Row,
    attempts: list[sqlite3.Row],
    *,
    conversation_paths: _ConversationPathLookup,
) -> OrchestrationRunResponse:
    repo_root = Path(str(row["repo_root"]))
    run_status = _normalize_persisted_run_status(row)
    tasks = _shape_persisted_tasks(
        attempts,
        repo_root=repo_root,
        run_status=run_status,
        conversation_paths=conversation_paths,
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
        mode="persisted",
        integration_branch="",
        task_pr_target="",
        final_pr_target="",
        status=run_status,
        stack_status=None,
        feature_branch=None,
        active_task_id=active_task_id,
        heartbeat_at=_isoformat(latest_heartbeat_at),
        finished_at=_isoformat(finished_at),
        planner=None,
        tasks=tasks,
        final_pr=None,
        operation_history=[],
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
    conversation_paths: _ConversationPathLookup,
) -> list[OrchestrationTaskResponse]:
    latest_attempts: dict[str, sqlite3.Row] = {}
    for row in attempts:
        task_id = str(row["task_id"])
        if task_id not in latest_attempts:
            latest_attempts[task_id] = row

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
                    conversation_paths=conversation_paths,
                ),
            )
        )
    return tasks


def _shape_persisted_invocation(
    row: sqlite3.Row,
    *,
    repo_root: Path,
    conversation_paths: _ConversationPathLookup,
) -> OrchestrationInvocationResponse | None:
    agent_value = row["agent"]
    session_id = str(row["session_id"]) if row["session_id"] is not None else None
    output_text = str(row["output_text"] or "")
    error_text = str(row["error"] or "")
    if agent_value not in {"claude", "codex"}:
        return None
    agent = cast(ProviderName, str(agent_value))
    project_path = _normalize_repo_project_path(str(repo_root), agent) if session_id else None
    conversation_path = conversation_paths.resolve(provider=agent, session_id=session_id)
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
def _normalize_persisted_run_status(row: sqlite3.Row) -> RunRuntimeStatus:
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
    materialized: MaterializedRuntimeRun | None = None,
) -> _ShapedRun:
    state = stored.state
    repo_root = state.repo_root
    is_stale = _is_stale_runtime_state(state)
    heartbeat_at = _isoformat(state.heartbeat_at)
    conversation_paths = _build_conversation_path_lookup(services)
    planner = _shape_invocation(state.planner, repo_root, conversation_paths=conversation_paths)
    materialized_attempts = _materialized_attempts_by_task(materialized)
    tasks = [
        _shape_runtime_task(
            task,
            repo_root,
            stale=is_stale,
            conversation_paths=conversation_paths,
            materialized_attempt=materialized_attempts.get(str(task.task_id)),
        )
        for task in state.tasks
    ]
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
        stack_status=state.stack_status,
        feature_branch=_shape_feature_branch(state),
        active_task_id=active_task_id,
        heartbeat_at=heartbeat_at,
        finished_at=_isoformat(state.finished_at),
        planner=planner,
        tasks=tasks,
        final_pr=_shape_final_pr(state),
        operation_history=[_shape_operation_history(entry) for entry in state.operation_history],
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
        **_extract_graph_v2_fields(state, materialized=materialized),
    )
    return _ShapedRun(response=response, last_updated_at=last_updated_at)


def _shape_run_record(
    stored: StoredOatsRunRecord,
    *,
    services: BackendServices | None = None,
) -> _ShapedRun:
    record = stored.record
    repo_root = record.repo_root
    conversation_paths = _build_conversation_path_lookup(services)
    planner = _shape_invocation(record.planner, repo_root, conversation_paths=conversation_paths)
    tasks = [
        _shape_record_task(task, repo_root, conversation_paths=conversation_paths)
        for task in record.tasks
    ]
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
        stack_status=None,
        feature_branch=None,
        active_task_id=None,
        heartbeat_at=_isoformat(recorded_at),
        finished_at=_isoformat(recorded_at),
        planner=planner,
        tasks=tasks,
        final_pr=None,
        operation_history=[],
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
    conversation_paths: _ConversationPathLookup,
    materialized_attempt: MaterializedTaskAttempt | None = None,
) -> OrchestrationTaskResponse:
    invocation = _shape_invocation(
        task.invocation,
        repo_root,
        fallback_agent=task.agent,
        fallback_role=task.role,
        conversation_paths=conversation_paths,
    )
    base_status = materialized_attempt.status if materialized_attempt is not None else task.status
    status: TaskRuntimeStatus = "pending" if stale and base_status == "running" else cast(TaskRuntimeStatus, base_status)
    return OrchestrationTaskResponse(
        task_id=task.task_id,
        title=task.title,
        depends_on=list(task.depends_on),
        parent_branch=task.parent_branch,
        status=status,
        attempts=task.attempts,
        task_pr=_shape_task_pr(task),
        operation_history=[_shape_operation_history(entry) for entry in task.operation_history],
        invocation=invocation,
    )


def _shape_record_task(
    task: TaskExecutionRecord,
    repo_root: Path,
    *,
    conversation_paths: _ConversationPathLookup,
) -> OrchestrationTaskResponse:
    invocation = _shape_invocation(task.invocation, repo_root, conversation_paths=conversation_paths)
    return OrchestrationTaskResponse(
        task_id=task.task_id,
        title=task.title,
        depends_on=list(task.depends_on),
        parent_branch=None,
        status=_derive_task_status(task.invocation),
        attempts=0,
        task_pr=None,
        operation_history=[],
        invocation=invocation,
    )


def _extract_graph_v2_fields(
    state: RunRuntimeState,
    *,
    materialized: MaterializedRuntimeRun | None = None,
) -> dict:
    """Extract graph-native v2 fields from runtime state.

    Returns a dict suitable for ** unpacking into OrchestrationRunResponse.
    Returns empty graph fields for v1 states (no graph).
    """
    if state.graph is None:
        return {}

    graph = state.graph
    nodes = [
        OrchestrationGraphNodeResponse(
            task_id=node.task_id,
            kind=node.kind.value,
            title=node.title,
            status=node.status,
            agent=node.agent,
            model=node.model,
            discovered_by=node.discovered_by,
        )
        for node in graph.nodes.values()
    ]
    edges = [
        OrchestrationTypedEdgeResponse(
            from_task=edge.from_task,
            to_task=edge.to_task,
            predicate=edge.predicate.value,
            satisfied=edge.satisfied,
        )
        for edge in graph.edges
    ]
    ready_queue = graph.ready_tasks()
    mutation_source = materialized.graph_mutations if materialized is not None else state.graph_mutations
    operator_source = (
        materialized.operator_actions
        if materialized is not None
        else project_operator_actions(state, list(mutation_source))
    )
    graph_mutations = [
        OrchestrationGraphMutationResponse(
            mutation_id=mutation.mutation_id,
            kind=mutation.kind,
            discovered_by=mutation.discovered_by,
            source=mutation.source,
            timestamp=_graph_mutation_timestamp(mutation),
            nodes_added=list(mutation.nodes_added),
        )
        for mutation in mutation_source
    ]
    operator_actions = [
        OrchestrationOperatorActionResponse(
            action=action.action,
            actor=action.actor,
            created_at=action.created_at,
            target_task_id=action.target_task_id,
            details=dict(action.details),
        )
        for action in operator_source
    ]
    graph_mutation_count = len(mutation_source)

    return {
        "nodes": nodes,
        "edges": edges,
        "ready_queue": ready_queue,
        "graph_mutation_count": graph_mutation_count,
        "graph_mutations": graph_mutations,
        "operator_actions": operator_actions,
        "last_checkpoint_at": _isoformat(state.updated_at),
    }


def _materialized_attempts_by_task(
    materialized: MaterializedRuntimeRun | None,
) -> dict[str, MaterializedTaskAttempt]:
    if materialized is None:
        return {}
    return {attempt.task_id: attempt for attempt in materialized.task_attempts}


def _graph_mutation_timestamp(mutation: GraphMutation | MaterializedGraphMutation) -> str:
    if isinstance(mutation, MaterializedGraphMutation):
        return mutation.timestamp or ""
    return _isoformat(mutation.timestamp) or ""


def _shape_feature_branch(state: RunRuntimeState) -> OrchestrationFeatureBranchResponse | None:
    if state.feature_branch is None:
        return None
    return OrchestrationFeatureBranchResponse(
        name=state.feature_branch.name,
        base_branch=state.feature_branch.base_branch,
    )


def _shape_task_pr(task: TaskRuntimeRecord) -> OrchestrationTaskPullRequestResponse | None:
    task_pr = task.task_pr
    if task_pr is None:
        return None
    review_summary = (
        OrchestrationReviewSummaryResponse(
            blocking_state=task_pr.review_summary.blocking_state,
            approvals=task_pr.review_summary.approvals,
            changes_requested=task_pr.review_summary.changes_requested,
        )
        if task_pr.review_summary is not None
        else None
    )
    return OrchestrationTaskPullRequestResponse(
        number=task_pr.number,
        url=task_pr.url,
        state=task_pr.state,
        merge_gate_status=task_pr.merge_gate_status,
        base_branch=task_pr.base_branch,
        head_branch=task_pr.head_branch,
        mergeability=task_pr.mergeability,
        checks_summary=dict(task_pr.checks_summary),
        review_summary=review_summary,
        snapshot_source=task_pr.snapshot_source,
        last_refreshed_at=_isoformat(task_pr.last_refreshed_at),
        is_stale=task_pr.is_stale,
    )


def _shape_final_pr(state: RunRuntimeState) -> OrchestrationFinalPullRequestResponse | None:
    final_pr = state.final_pr
    if final_pr is None:
        return None
    return OrchestrationFinalPullRequestResponse(
        number=final_pr.number,
        url=final_pr.url,
        state=final_pr.state,
        review_gate_status=final_pr.review_gate_status,
        base_branch=final_pr.base_branch,
        head_branch=final_pr.head_branch,
        checks_summary=dict(final_pr.checks_summary),
        snapshot_source=final_pr.snapshot_source,
        last_refreshed_at=_isoformat(final_pr.last_refreshed_at),
        is_stale=final_pr.is_stale,
    )


def _shape_operation_history(entry) -> OrchestrationOperationHistoryResponse:
    return OrchestrationOperationHistoryResponse(
        kind=entry.kind,
        status=entry.status,
        session_id=entry.session_id,
        started_at=_isoformat(entry.started_at) or "",
        finished_at=_isoformat(entry.finished_at),
        details=dict(entry.details),
    )


def _shape_invocation(
    invocation: AgentInvocationResult | InvocationRuntimeRecord | None,
    repo_root: Path,
    *,
    fallback_agent: ProviderName | None = None,
    fallback_role: str | None = None,
    conversation_paths: _ConversationPathLookup,
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
    conversation_path = conversation_paths.resolve(provider=agent, session_id=session_id)
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


def _build_conversation_path_lookup(services: BackendServices | None) -> _ConversationPathLookup:
    paths_by_identity: dict[tuple[ProviderName, str], str | None] = {}
    if services is None:
        return _ConversationPathLookup(services=None, paths_by_identity=paths_by_identity)

    app_sqlite_store = getattr(services, "app_sqlite_store", None)
    if app_sqlite_store is None:
        return _ConversationPathLookup(services=services, paths_by_identity=paths_by_identity)

    for summary in app_sqlite_store.list_historical_conversations():
        provider = cast(ProviderName, summary.provider)
        key = (provider, summary.session_id)
        if key in paths_by_identity:
            continue
        paths_by_identity[key] = _conversation_path_from_ref(
            build_conversation_ref(summary.route_slug, summary.provider, summary.session_id)
        )

    return _ConversationPathLookup(services=services, paths_by_identity=paths_by_identity)


def _conversation_path_from_ref(conversation_ref: str) -> str:
    return f"/conversations/by-ref/{quote(conversation_ref, safe='')}"


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
