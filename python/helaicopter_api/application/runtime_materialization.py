"""Materialize authoritative live runtime artifacts into operator-facing views."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.runtime_materialization import (
    MaterializedDispatchEvent,
    MaterializedGraphMutation,
    MaterializedOperatorAction,
    MaterializedRuntimeRun,
    MaterializedTaskAttempt,
)
from oats.graph import GraphMutation
from oats.models import OperationHistoryEntry, RunRuntimeState

_RUNTIME_STATE_ADAPTER = TypeAdapter(RunRuntimeState)
_GRAPH_MUTATION_ADAPTER = TypeAdapter(GraphMutation)
_DICT_ADAPTER = TypeAdapter(dict[str, object])

_OPERATOR_MUTATION_ACTIONS = {
    "pause_run": "pause",
    "cancel_task": "cancel",
    "force_retry_task": "retry",
    "reroute_task": "reroute",
    "insert_tasks": "insert",
}

_OPERATION_HISTORY_ACTIONS = {
    "resume": "resume",
}


def get_materialized_runtime_run(
    services: BackendServices,
    run_id: str,
) -> MaterializedRuntimeRun:
    """Return one materialized runtime payload by run ID."""
    stored = services.oats_run_store.get_runtime_state(run_id)
    if stored is None:
        raise ValueError(f"OATS runtime state not found for run '{run_id}'")
    return materialize_runtime_run(stored.path.parent)


def materialize_runtime_run(run_dir: Path) -> MaterializedRuntimeRun:
    """Read one runtime directory into a stable materialized view."""
    state = _RUNTIME_STATE_ADAPTER.validate_json((run_dir / "state.json").read_bytes())
    task_attempts = _load_task_attempts(run_dir, state)
    graph_mutations = _load_graph_mutations(run_dir, state)
    dispatch_events = _load_dispatch_events(run_dir.parent, run_id=str(state.run_id))
    operator_actions = project_operator_actions(state, graph_mutations)
    return MaterializedRuntimeRun(
        run_id=str(state.run_id),
        source="runtime",
        task_attempts=task_attempts,
        graph_mutations=graph_mutations,
        dispatch_events=dispatch_events,
        operator_actions=operator_actions,
    )


def _load_task_attempts(run_dir: Path, state: RunRuntimeState) -> list[MaterializedTaskAttempt]:
    results_dir = run_dir / "results"
    attempts: list[MaterializedTaskAttempt] = []
    for task in state.tasks:
        result_path = results_dir / f"{task.task_id}.json"
        if result_path.exists():
            payload = _DICT_ADAPTER.validate_json(result_path.read_bytes())
            attempts.append(
                MaterializedTaskAttempt(
                    task_id=str(payload.get("task_id") or task.task_id),
                    attempt_id=_string(payload.get("attempt_id")),
                    worker_id=_string(payload.get("worker_id")),
                    provider_session_id=_string(payload.get("provider_session_id")),
                    session_reused=bool(payload.get("session_reused")),
                    session_status_after_task=_string(payload.get("session_status_after_task")),
                    status=_string(payload.get("status")) or task.status,
                    duration_seconds=_float(payload.get("duration_seconds")),
                    branch_name=_string(payload.get("branch_name")),
                    commit_sha=_string(payload.get("commit_sha")),
                    error_summary=_string(payload.get("error_summary")),
                )
            )
            continue

        attempts.append(
            MaterializedTaskAttempt(
                task_id=str(task.task_id),
                status=task.status,
            )
        )
    return attempts


def _load_graph_mutations(run_dir: Path, state: RunRuntimeState) -> list[MaterializedGraphMutation]:
    path = run_dir / "graph_mutations.jsonl"
    if path.exists():
        mutations: list[MaterializedGraphMutation] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            mutation = _GRAPH_MUTATION_ADAPTER.validate_python(json.loads(line))
            mutations.append(
                MaterializedGraphMutation(
                    mutation_id=mutation.mutation_id,
                    kind=mutation.kind,
                    discovered_by=mutation.discovered_by,
                    source=mutation.source,
                    timestamp=mutation.timestamp.isoformat() if mutation.timestamp else None,
                    nodes_added=list(mutation.nodes_added),
                )
            )
        return mutations

    return [
        MaterializedGraphMutation(
            mutation_id=mutation.mutation_id,
            kind=mutation.kind,
            discovered_by=mutation.discovered_by,
            source=mutation.source,
            timestamp=mutation.timestamp.isoformat() if mutation.timestamp else None,
            nodes_added=list(mutation.nodes_added),
        )
        for mutation in state.graph_mutations
    ]


def _load_dispatch_events(runtime_root: Path, *, run_id: str) -> list[MaterializedDispatchEvent]:
    path = runtime_root / "dispatch_history.jsonl"
    if not path.exists():
        return []

    events: list[MaterializedDispatchEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = _DICT_ADAPTER.validate_python(json.loads(line))
        if _string(payload.get("run_id")) != run_id:
            continue
        events.append(
            MaterializedDispatchEvent(
                run_id=run_id,
                task_id=_string(payload.get("task_id")) or "",
                worker_id=_string(payload.get("worker_id")) or "",
                provider=_string(payload.get("provider")) or "",
                model=_string(payload.get("model")) or "",
                dispatched_at=_string(payload.get("dispatched_at")) or "",
            )
        )
    return events


def project_operator_actions(
    state: RunRuntimeState,
    graph_mutations: list[GraphMutation | MaterializedGraphMutation],
) -> list[MaterializedOperatorAction]:
    """Project durable operator actions from runtime mutations and history."""
    tasks_by_id = {str(task.task_id): task for task in state.tasks}
    actions: list[MaterializedOperatorAction] = []

    for mutation in graph_mutations:
        action = _OPERATOR_MUTATION_ACTIONS.get(mutation.kind)
        if action is None or mutation.source != "operator":
            continue
        target_task_id = mutation.nodes_added[0] if mutation.nodes_added else None
        actions.append(
            MaterializedOperatorAction(
                action=action,
                actor=mutation.discovered_by or "operator",
                created_at=_graph_mutation_created_at(mutation),
                target_task_id=target_task_id,
                details=_operator_action_details(
                    action,
                    state=state,
                    target_task_id=target_task_id,
                    tasks_by_id=tasks_by_id,
                ),
            )
        )

    for entry in state.operation_history:
        action = _OPERATION_HISTORY_ACTIONS.get(entry.kind)
        if action is None:
            continue
        actions.append(_action_from_operation_history(entry, action=action))

    actions.sort(key=lambda item: item.created_at)
    return actions


def _action_from_operation_history(
    entry: OperationHistoryEntry,
    *,
    action: str,
) -> MaterializedOperatorAction:
    details = dict(entry.details)
    target_task_id = _string(details.get("task_id"))
    details.setdefault("status", entry.status)
    return MaterializedOperatorAction(
        action=action,
        actor="operator",
        created_at=entry.started_at.isoformat(),
        target_task_id=target_task_id,
        details=details,
    )


def _operator_action_details(
    action: str,
    *,
    state: RunRuntimeState,
    target_task_id: str | None,
    tasks_by_id: dict[str, object],
) -> dict[str, object]:
    if target_task_id is None:
        return {}
    task = tasks_by_id.get(target_task_id)
    if task is None:
        return {}

    details: dict[str, object] = {"taskId": target_task_id}
    agent = _string(getattr(task, "agent", None))
    model = None
    if state.graph is not None and target_task_id in state.graph.nodes:
        graph_node = state.graph.nodes[target_task_id]
        agent = _string(graph_node.agent) or agent
        model = _string(graph_node.model)
    if action == "reroute":
        if agent is not None:
            details["provider"] = agent
        if model is not None:
            details["model"] = model
    return details


def _graph_mutation_created_at(mutation: GraphMutation | MaterializedGraphMutation) -> str:
    if isinstance(mutation, MaterializedGraphMutation):
        return mutation.timestamp or ""
    return mutation.timestamp.isoformat() if mutation.timestamp is not None else ""


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _float(value: object) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    return None
