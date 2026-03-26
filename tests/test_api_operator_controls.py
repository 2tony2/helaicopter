"""Focused API coverage for durable operator control actions."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator

from fastapi.testclient import TestClient
from pydantic import BaseModel

from helaicopter_api.adapters.oats_artifacts import FileOatsRunStore
from helaicopter_api.application.orchestration import get_oats_run
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.server.config import Settings
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app
from oats.graph import EdgePredicate, GraphMutation, TaskGraph, TaskKind, TaskNode, TypedEdge
from oats.models import OperationHistoryEntry, RunRuntimeState, TaskRuntimeRecord


def _write_model(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


@contextmanager
def orchestration_client(project_root: Path, **service_attrs: object) -> Iterator[TestClient]:
    application = create_app()
    store = FileOatsRunStore(
        project_root=project_root,
        runtime_dir=project_root / ".oats" / "runtime",
    )
    settings = service_attrs.pop("settings", None) or Settings(project_root=project_root)
    application.dependency_overrides[get_services] = lambda: _services_stub(
        oats_run_store=store,
        settings=settings,
        **service_attrs,
    )
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.dependency_overrides.clear()


def _build_runtime_state_with_graph(tmp_path: Path) -> RunRuntimeState:
    now = datetime.now(UTC)
    repo_root = tmp_path

    graph = TaskGraph()
    for tid in ["auth", "models", "api", "dashboard", "e2e"]:
        graph.add_node(TaskNode(task_id=tid, kind=TaskKind.IMPLEMENTATION, title=tid.upper()))
    graph.add_edge(TypedEdge(from_task="auth", to_task="api", predicate=EdgePredicate.CODE_READY))
    graph.add_edge(TypedEdge(from_task="models", to_task="api", predicate=EdgePredicate.CODE_READY))
    graph.add_edge(TypedEdge(from_task="api", to_task="dashboard", predicate=EdgePredicate.CODE_READY))
    graph.add_edge(TypedEdge(from_task="api", to_task="e2e", predicate=EdgePredicate.PR_MERGED))
    graph.record_task_success("auth")
    graph.evaluate_edges_from("auth")

    return RunRuntimeState(
        contract_version="oats-runtime-v2",
        run_id="run_abc",
        run_title="Graph test run",
        repo_root=repo_root,
        config_path=repo_root / ".oats" / "config.toml",
        run_spec_path=repo_root / "runs" / "test.md",
        mode="writable",
        integration_branch="oats/overnight/graph-test",
        task_pr_target="oats/overnight/graph-test",
        final_pr_target="main",
        runtime_dir=repo_root / ".oats" / "runtime" / "run_abc",
        status="running",
        started_at=now - timedelta(minutes=10),
        updated_at=now - timedelta(seconds=5),
        heartbeat_at=now - timedelta(seconds=5),
        tasks=[
            TaskRuntimeRecord(
                task_id=tid,
                title=tid.upper(),
                branch_name=f"oats/task/{tid}",
                pr_base="oats/overnight/graph-test",
                agent="claude",
                status="succeeded" if tid == "auth" else "pending",
            )
            for tid in ["auth", "models", "api", "dashboard", "e2e"]
        ],
        graph=graph,
        graph_mutations=[],
    )


def test_operator_pause_retry_and_reroute_are_materialized_in_action_responses(tmp_path: Path) -> None:
    state = _build_runtime_state_with_graph(tmp_path)
    state_path = tmp_path / ".oats" / "runtime" / state.run_id / "state.json"
    _write_model(state_path, state)

    with orchestration_client(tmp_path) as client:
        paused = client.post(f"/orchestration/oats/{state.run_id}/pause")
        retried = client.post(f"/orchestration/oats/{state.run_id}/tasks/api/force-retry")
        rerouted = client.post(
            f"/orchestration/oats/{state.run_id}/tasks/api/reroute",
            json={"provider": "codex", "model": "o3-pro"},
        )

    assert paused.status_code == 200
    assert retried.status_code == 200
    assert rerouted.status_code == 200
    payload = rerouted.json()
    assert [action["action"] for action in payload["operatorActions"]] == [
        "pause",
        "retry",
        "reroute",
    ]
    assert payload["operatorActions"][-1]["details"]["provider"] == "codex"
    assert payload["operatorActions"][-1]["details"]["model"] == "o3-pro"


def test_operator_resume_from_operation_history_is_projected_on_run_detail(tmp_path: Path) -> None:
    state = _build_runtime_state_with_graph(tmp_path)
    now = datetime.now(UTC)
    state.operation_history.append(
        OperationHistoryEntry(
            kind="resume",
            status="succeeded",
            started_at=now - timedelta(minutes=1),
            finished_at=now,
            details={"task_id": "api"},
        )
    )
    state.graph_mutations.append(
        GraphMutation(
            mutation_id="mut_pause",
            kind="pause_run",
            discovered_by="operator",
            source="operator",
            timestamp=now - timedelta(minutes=2),
            nodes_added=["api"],
        )
    )
    state_path = tmp_path / ".oats" / "runtime" / state.run_id / "state.json"
    _write_model(state_path, state)

    services = _services_stub(
        oats_run_store=type(
            "StoreStub",
            (),
            {
                "get_runtime_state": lambda self, run_id: type(
                    "Stored",
                    (),
                    {"path": state_path, "state": state},
                )(),
                "list_runtime_states": lambda self: [
                    type("Stored", (), {"path": state_path, "state": state})()
                ]
            },
        )()
    )

    payload = get_oats_run(services, state.run_id).model_dump(mode="json", by_alias=True)

    assert [action["action"] for action in payload["operatorActions"]] == ["pause", "resume"]
    assert payload["operatorActions"][1]["targetTaskId"] == "api"
