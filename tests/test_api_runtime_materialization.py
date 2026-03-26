from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator

from fastapi.testclient import TestClient
from pydantic import BaseModel

from helaicopter_api.adapters.oats_artifacts import FileOatsRunStore
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.server.config import Settings
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app
from oats.graph import GraphMutation, TaskGraph, TaskKind, TaskNode
from oats.models import OperationHistoryEntry, RunRuntimeState, TaskRuntimeRecord


def _write_model(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


def _write_runtime_fixture(project_root: Path) -> None:
    run_dir = project_root / ".oats" / "runtime" / "run_1"
    now = datetime.now(UTC)
    graph = TaskGraph()
    graph.add_node(
        TaskNode(
            task_id="task_auth",
            kind=TaskKind.IMPLEMENTATION,
            title="Implement auth",
            status="running",
            agent="claude",
            model="claude-sonnet-4-6",
        )
    )
    state = RunRuntimeState(
        run_id="run_1",
        run_title="Runtime materialization",
        repo_root=project_root,
        config_path=project_root / ".oats" / "config.toml",
        run_spec_path=project_root / "runs" / "runtime.md",
        mode="writable",
        integration_branch="oats/phase2/runtime",
        task_pr_target="oats/phase2/runtime",
        final_pr_target="main",
        runtime_dir=run_dir,
        status="running",
        started_at=now - timedelta(minutes=5),
        updated_at=now - timedelta(seconds=15),
        heartbeat_at=now - timedelta(seconds=5),
        tasks=[
            TaskRuntimeRecord(
                task_id="task_auth",
                title="Implement auth",
                depends_on=[],
                branch_name="oats/task/task_auth",
                parent_branch="main",
                pr_base="main",
                agent="claude",
                status="running",
                attempts=2,
            )
        ],
        graph=graph,
        graph_mutations=[
            GraphMutation(
                mutation_id="mut_1",
                kind="pause_run",
                discovered_by="operator",
                source="operator",
                nodes_added=["task_auth"],
            )
        ],
        operation_history=[
            OperationHistoryEntry(
                kind="resume",
                status="succeeded",
                details={"task_id": "task_auth"},
            )
        ],
    )
    _write_model(run_dir / "state.json", state)
    (run_dir / "graph_mutations.jsonl").write_text(
        (
            '{"mutation_id":"mut_1","kind":"pause_run","discovered_by":"operator",'
            f'"source":"operator","timestamp":"{now.isoformat()}","nodes_added":["task_auth"],"edges_added":[]}}\n'
        ),
        encoding="utf-8",
    )
    (project_root / ".oats" / "runtime" / "dispatch_history.jsonl").write_text(
        (
            '{"run_id":"run_1","task_id":"task_auth","worker_id":"wkr_1",'
            f'"provider":"claude","model":"claude-sonnet-4-6","dispatched_at":"{now.isoformat()}"}}\n'
        ),
        encoding="utf-8",
    )
    (run_dir / "results").mkdir(parents=True, exist_ok=True)
    (run_dir / "results" / "task_auth.json").write_text(
        (
            '{"task_id":"task_auth","run_id":"run_1","worker_id":"wkr_1","status":"succeeded",'
            '"duration_seconds":42.0,"attempt_id":"att_2","branch_name":"oats/task/task_auth",'
            '"commit_sha":"abc123","error_summary":null,'
            '"provider_session_id":"sess_provider_1","session_reused":true,'
            '"session_status_after_task":"ready"}'
        ),
        encoding="utf-8",
    )


@contextmanager
def runtime_materialization_client(project_root: Path) -> Iterator[TestClient]:
    application = create_app()
    store = FileOatsRunStore(
        project_root=project_root,
        runtime_dir=project_root / ".oats" / "runtime",
    )
    settings = Settings(project_root=project_root)
    application.dependency_overrides[get_services] = lambda: _services_stub(
        oats_run_store=store,
        settings=settings,
    )
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.dependency_overrides.clear()


def test_runtime_materialization_endpoint_returns_live_attempts_and_mutations(tmp_path: Path) -> None:
    _write_runtime_fixture(tmp_path)

    with runtime_materialization_client(tmp_path) as client:
        response = client.get("/orchestration/runtime/run_1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["taskAttempts"][0]["taskId"] == "task_auth"
    assert payload["taskAttempts"][0]["attemptId"] == "att_2"
    assert payload["taskAttempts"][0]["providerSessionId"] == "sess_provider_1"
    assert payload["taskAttempts"][0]["sessionReused"] is True
    assert payload["taskAttempts"][0]["sessionStatusAfterTask"] == "ready"
    assert payload["graphMutations"][0]["source"] == "operator"
    assert payload["dispatchEvents"][0]["workerId"] == "wkr_1"
    assert payload["operatorActions"][0]["action"] == "pause"
    assert payload["operatorActions"][1]["action"] == "resume"


def test_runtime_materialization_survives_reload_and_preserves_attempt_history(tmp_path: Path) -> None:
    _write_runtime_fixture(tmp_path)

    with runtime_materialization_client(tmp_path) as client:
        first = client.get("/orchestration/runtime/run_1")

    with runtime_materialization_client(tmp_path) as client:
        second = client.get("/orchestration/runtime/run_1")

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["taskAttempts"][0]["attemptId"] == "att_2"
    assert second_payload["taskAttempts"][0]["attemptId"] == "att_2"
    assert first_payload["dispatchEvents"][0]["workerId"] == "wkr_1"
    assert second_payload["graphMutations"][0]["mutationId"] == "mut_1"
