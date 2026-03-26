"""High-signal orchestration smoke scenarios for provider-complete local operation."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session

from helaicopter_api.adapters.oats_artifacts import FileOatsRunStore
from helaicopter_api.application.auth import create_credential
from helaicopter_api.application.dispatch import InMemoryWorkerRegistry
from helaicopter_api.application.resolver import ResolverLoop
from helaicopter_api.application.runtime_materialization import materialize_runtime_run
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.auth import CreateCredentialRequest
from helaicopter_api.server.config import Settings
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app
from helaicopter_db.models.oltp import OltpBase, WorkerRegistryRecord
from oats.graph import TaskGraph, TaskKind, TaskNode
from oats.models import RunRuntimeState, TaskRuntimeRecord


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


def _run(coro):  # noqa: ANN001, ANN202
    return asyncio.run(coro)


def _write_runtime_state(
    project_root: Path,
    *,
    run_id: str,
    task_id: str,
    provider: str,
    model: str,
) -> Path:
    run_dir = project_root / ".oats" / "runtime" / run_id
    now = datetime.now(UTC)
    graph = TaskGraph()
    graph.add_node(
        TaskNode(
            task_id=task_id,
            kind=TaskKind.IMPLEMENTATION,
            title=task_id,
            status="pending",
            agent=provider,
            model=model,
        )
    )
    state = RunRuntimeState(
        run_id=run_id,
        run_title=f"Smoke {provider}",
        repo_root=project_root,
        config_path=project_root / ".oats" / "config.toml",
        run_spec_path=project_root / "runs" / f"{run_id}.md",
        mode="writable",
        integration_branch=f"oats/{run_id}",
        task_pr_target=f"oats/{run_id}",
        final_pr_target="main",
        runtime_dir=run_dir,
        status="running",
        started_at=now - timedelta(minutes=5),
        updated_at=now - timedelta(seconds=5),
        heartbeat_at=now - timedelta(seconds=1),
        tasks=[
            TaskRuntimeRecord(
                task_id=task_id,
                title=task_id,
                depends_on=[],
                branch_name=f"oats/task/{task_id}",
                parent_branch="main",
                pr_base="main",
                agent=provider,
                status="pending",
                attempts=1,
            )
        ],
        graph=graph,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "state.json").write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return run_dir


@contextmanager
def _smoke_client(project_root: Path) -> Iterator[TestClient]:
    application = create_app()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    OltpBase.metadata.create_all(engine)
    registry = InMemoryWorkerRegistry()
    runtime_dir = project_root / ".oats" / "runtime"
    store = FileOatsRunStore(project_root=project_root, runtime_dir=runtime_dir)
    resolver = ResolverLoop(registry=registry, sqlite_engine=engine, runtime_dir=runtime_dir)
    resolver._running = True
    settings = Settings(project_root=project_root)

    application.dependency_overrides[get_services] = lambda: _services_stub(
        sqlite_engine=engine,
        oats_run_store=store,
        settings=settings,
    )
    try:
        with TestClient(application) as client:
            background_resolver = getattr(client.app.state, "resolver", None)
            if background_resolver is not None:
                background_resolver.stop()
            client.app.state.resolver = resolver
            client.app.state.worker_registry = registry
            client.app.state.settings = settings
            yield client
    finally:
        application.dependency_overrides.clear()
        engine.dispose()


def _register_worker(client: TestClient, *, provider: str, model: str) -> str:
    response = client.post(
        "/workers/register",
        json={
            "workerType": "pi_shell",
            "provider": provider,
            "capabilities": {
                "provider": provider,
                "models": [model],
                "maxConcurrentTasks": 1,
                "supportsDiscovery": False,
                "supportsResume": True,
                "tags": [],
            },
            "host": "local",
            "pid": 12345,
        },
    )
    assert response.status_code == 201
    return response.json()["workerId"]


def test_smoke_cold_start_to_healthy_system(tmp_path: Path) -> None:
    with _smoke_client(tmp_path) as client:
        _register_worker(client, provider="claude", model="claude-sonnet-4-6")
        _register_worker(client, provider="codex", model="o3-pro")
        engine = client.app.dependency_overrides[get_services]().sqlite_engine
        create_credential(
            engine,
            CreateCredentialRequest.model_validate(
                {
                    "provider": "claude",
                    "credentialType": "local_cli_session",
                    "cliConfigPath": "~/.claude",
                }
            ),
        )
        create_credential(
            engine,
            CreateCredentialRequest.model_validate(
                {
                    "provider": "codex",
                    "credentialType": "local_cli_session",
                    "cliConfigPath": "~/.codex",
                }
            ),
        )

        response = client.get("/operator/bootstrap")

    assert response.status_code == 200
    payload = response.json()
    assert payload["overallStatus"] == "ready"
    assert payload["resolverRunning"] is True
    assert {provider["provider"] for provider in payload["providers"]} == {"claude", "codex"}


def test_smoke_queue_stays_deferred_when_provider_credentials_are_missing(tmp_path: Path) -> None:
    _write_runtime_state(
        tmp_path,
        run_id="run_codex",
        task_id="task_codex",
        provider="codex",
        model="o3-pro",
    )

    with _smoke_client(tmp_path) as client:
        _register_worker(client, provider="codex", model="o3-pro")
        resolver = client.app.state.resolver

        graph = TaskGraph()
        graph.add_node(
            TaskNode(
                task_id="task_codex",
                title="task_codex",
                kind=TaskKind.IMPLEMENTATION,
                agent="codex",
                model="o3-pro",
            )
        )
        resolver.submit_graph("run_codex", graph)
        resolver._task_agents["task_codex"] = "codex"
        resolver._task_models["task_codex"] = "o3-pro"

        response = client.get("/dispatch/queue")

        assert response.status_code == 200
        payload = response.json()
        assert payload["ready"] == []
        assert payload["deferred"][0]["reason"] == "provider_not_ready"


def test_smoke_claude_and_codex_happy_paths_materialize_runtime_truth(tmp_path: Path) -> None:
    claude_run_dir = _write_runtime_state(
        tmp_path,
        run_id="run_claude",
        task_id="task_claude",
        provider="claude",
        model="claude-sonnet-4-6",
    )
    codex_run_dir = _write_runtime_state(
        tmp_path,
        run_id="run_codex",
        task_id="task_codex",
        provider="codex",
        model="o3-pro",
    )

    with _smoke_client(tmp_path) as client:
        claude_worker_id = _register_worker(client, provider="claude", model="claude-sonnet-4-6")
        codex_worker_id = _register_worker(client, provider="codex", model="o3-pro")
        resolver = client.app.state.resolver

        claude_graph = TaskGraph()
        claude_graph.add_node(
            TaskNode(
                task_id="task_claude",
                title="task_claude",
                kind=TaskKind.IMPLEMENTATION,
                agent="claude",
                model="claude-sonnet-4-6",
            )
        )
        codex_graph = TaskGraph()
        codex_graph.add_node(
            TaskNode(
                task_id="task_codex",
                title="task_codex",
                kind=TaskKind.IMPLEMENTATION,
                agent="codex",
                model="o3-pro",
            )
        )
        resolver.submit_graph("run_claude", claude_graph)
        resolver.submit_graph("run_codex", codex_graph)
        resolver._task_agents.update(
            {
                "task_claude": "claude",
                "task_codex": "codex",
            }
        )
        resolver._task_models.update(
            {
                "task_claude": "claude-sonnet-4-6",
                "task_codex": "o3-pro",
            }
        )

        claude_envelope = client.get(f"/workers/{claude_worker_id}/next-task")
        codex_envelope = client.get(f"/workers/{codex_worker_id}/next-task")
        assert claude_envelope.status_code == 200
        assert codex_envelope.status_code == 200

        claude_attempt = claude_envelope.json()["attemptId"]
        codex_attempt = codex_envelope.json()["attemptId"]

        assert client.post(
            f"/workers/{claude_worker_id}/report",
            json={
                "taskId": "task_claude",
                "attemptId": claude_attempt,
                "status": "succeeded",
                "durationSeconds": 5.0,
                "branchName": "oats/task/task_claude",
                "commitSha": "abc123",
            },
        ).status_code == 200
        assert client.post(
            f"/workers/{codex_worker_id}/report",
            json={
                "taskId": "task_codex",
                "attemptId": codex_attempt,
                "status": "succeeded",
                "durationSeconds": 7.0,
                "branchName": "oats/task/task_codex",
                "commitSha": "def456",
            },
        ).status_code == 200

    claude_runtime = materialize_runtime_run(claude_run_dir)
    codex_runtime = materialize_runtime_run(codex_run_dir)
    assert claude_runtime.task_attempts[0].status == "succeeded"
    assert codex_runtime.task_attempts[0].status == "succeeded"
    assert claude_runtime.dispatch_events[0].worker_id == claude_worker_id
    assert codex_runtime.dispatch_events[0].worker_id == codex_worker_id


def test_smoke_worker_interruption_is_visible_and_recoverable(tmp_path: Path) -> None:
    _write_runtime_state(
        tmp_path,
        run_id="run_retry",
        task_id="task_retry",
        provider="claude",
        model="claude-sonnet-4-6",
    )

    with _smoke_client(tmp_path) as client:
        worker_a = _register_worker(client, provider="claude", model="claude-sonnet-4-6")
        worker_b = _register_worker(client, provider="claude", model="claude-sonnet-4-6")
        resolver = client.app.state.resolver
        graph = TaskGraph()
        graph.add_node(
            TaskNode(
                task_id="task_retry",
                title="task_retry",
                kind=TaskKind.IMPLEMENTATION,
                agent="claude",
                model="claude-sonnet-4-6",
            )
        )
        resolver.submit_graph("run_retry", graph)

        dispatched = None
        for candidate in (worker_a, worker_b):
            response = client.get(f"/workers/{candidate}/next-task")
            if response.status_code == 200:
                dispatched = candidate
                break

        assert dispatched is not None
        engine = client.app.dependency_overrides[get_services]().sqlite_engine
        with Session(engine) as session:
            row = session.get(WorkerRegistryRecord, dispatched)
            assert row is not None
            row.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=10)
            session.commit()

        _run(resolver.tick())

        queue_response = client.get("/dispatch/queue")
        assert queue_response.status_code == 200
        deferred = queue_response.json()["deferred"]
        assert deferred == []
        healthy_workers = [item for item in client.get("/workers").json() if item["status"] != "dead"]
        assert healthy_workers
        assert graph.get_node("task_retry").status == "running"


def test_smoke_worker_interruption_without_spare_worker_is_retryable(tmp_path: Path) -> None:
    _write_runtime_state(
        tmp_path,
        run_id="run_retry_waiting",
        task_id="task_waiting",
        provider="claude",
        model="claude-sonnet-4-6",
    )

    with _smoke_client(tmp_path) as client:
        worker_id = _register_worker(client, provider="claude", model="claude-sonnet-4-6")
        resolver = client.app.state.resolver
        graph = TaskGraph()
        graph.add_node(
            TaskNode(
                task_id="task_waiting",
                title="task_waiting",
                kind=TaskKind.IMPLEMENTATION,
                agent="claude",
                model="claude-sonnet-4-6",
            )
        )
        resolver.submit_graph("run_retry_waiting", graph)

        response = client.get(f"/workers/{worker_id}/next-task")
        assert response.status_code == 200
        engine = client.app.dependency_overrides[get_services]().sqlite_engine
        with Session(engine) as session:
            row = session.get(WorkerRegistryRecord, worker_id)
            assert row is not None
            row.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=10)
            session.commit()
        worker = resolver._registry.get(worker_id)
        assert worker is not None
        worker.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=10)

        _run(resolver.tick())

        queue_response = client.get("/dispatch/queue")
        assert queue_response.status_code == 200
        deferred = queue_response.json()["deferred"]
        assert deferred[0]["reason"] == "worker_interrupted"
        assert deferred[0]["canRetry"] is True
