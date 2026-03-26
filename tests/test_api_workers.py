"""Endpoint tests for the worker registry API."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.application.dispatch import InMemoryWorkerRegistry
from helaicopter_api.application.resolver import ResolverLoop
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app
from helaicopter_db.models.oltp import OltpBase
from helaicopter_db.models.oltp import WorkerRegistryRecord
from oats.graph import TaskGraph, TaskKind, TaskNode


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


@contextmanager
def _worker_client() -> Iterator[TestClient]:
    """Test client with an in-memory SQLite engine for worker registry tests."""
    application = create_app()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    OltpBase.metadata.create_all(engine)

    application.dependency_overrides[get_services] = lambda: _services_stub(
        sqlite_engine=engine,
    )
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.dependency_overrides.clear()
        engine.dispose()


_REGISTRATION_PAYLOAD = {
    "workerType": "pi_shell",
    "provider": "claude",
    "capabilities": {
        "provider": "claude",
        "models": ["claude-sonnet-4-6", "claude-opus-4-6"],
        "maxConcurrentTasks": 1,
        "supportsDiscovery": True,
        "supportsResume": True,
        "tags": [],
    },
    "host": "local",
    "pid": 12345,
}


def _make_resolver(*, task_id: str = "auth", run_id: str = "run_abc") -> ResolverLoop:
    graph = TaskGraph()
    graph.add_node(
        TaskNode(
            task_id=task_id,
            kind=TaskKind.IMPLEMENTATION,
            title="Auth Service Setup",
            acceptance_criteria=["All tests pass"],
        )
    )
    return ResolverLoop(
        registry=InMemoryWorkerRegistry(),
        graphs={run_id: graph},
        task_agents={task_id: "claude"},
        task_models={task_id: "claude-sonnet-4-6"},
    )


def _register_worker(client: TestClient, **overrides: object) -> str:
    payload = {**_REGISTRATION_PAYLOAD, **overrides}
    response = client.post("/workers/register", json=payload)
    assert response.status_code == 201
    return response.json()["workerId"]


# ---- Registration ----


def test_register_worker_returns_worker_id() -> None:
    with _worker_client() as client:
        response = client.post("/workers/register", json=_REGISTRATION_PAYLOAD)
        assert response.status_code == 201
        payload = response.json()
        assert payload["workerId"].startswith("wkr_")
        assert payload["status"] == "idle"


def test_register_worker_appears_in_list() -> None:
    with _worker_client() as client:
        worker_id = _register_worker(client)
        response = client.get("/workers")
        assert response.status_code == 200
        workers = response.json()
        assert worker_id in [w["workerId"] for w in workers]


# ---- Heartbeat ----


def test_heartbeat_updates_last_seen() -> None:
    with _worker_client() as client:
        worker_id = _register_worker(client)
        response = client.post(f"/workers/{worker_id}/heartbeat", json={"status": "idle"})
        assert response.status_code == 200


def test_heartbeat_unknown_worker_returns_404() -> None:
    with _worker_client() as client:
        response = client.post("/workers/wkr_nonexistent/heartbeat", json={"status": "idle"})
        assert response.status_code == 404


# ---- Deregister ----


def test_deregister_worker() -> None:
    with _worker_client() as client:
        worker_id = _register_worker(client)
        response = client.delete(f"/workers/{worker_id}")
        assert response.status_code == 204
        # Verify gone
        response = client.get("/workers")
        workers = response.json()
        assert worker_id not in [w["workerId"] for w in workers]


# ---- List with filter ----


def test_list_workers_filters_by_provider() -> None:
    with _worker_client() as client:
        _register_worker(client, provider="claude")
        _register_worker(client, provider="codex", capabilities={
            "provider": "codex",
            "models": ["codex-mini"],
            "maxConcurrentTasks": 1,
            "supportsDiscovery": False,
            "supportsResume": False,
            "tags": [],
        })
        response = client.get("/workers?provider=claude")
        workers = response.json()
        assert len(workers) >= 1
        assert all(w["provider"] == "claude" for w in workers)


# ---- Drain ----


def test_drain_worker() -> None:
    with _worker_client() as client:
        worker_id = _register_worker(client)
        response = client.post(f"/workers/{worker_id}/drain")
        assert response.status_code == 200
        # Worker should be draining
        response = client.get(f"/workers/{worker_id}")
        assert response.json()["status"] == "draining"


def test_report_result_preserves_draining_status(tmp_path: Path) -> None:
    with _worker_client() as client:
        worker_id = _register_worker(client)
        resolver = _make_resolver()
        client.app.state.resolver = resolver
        client.app.state.worker_registry = resolver._registry
        runtime_dir = tmp_path / ".oats" / "runtime"
        client.app.state.settings = type(
            "SettingsStub",
            (),
            {"runtime_dir": runtime_dir},
        )()

        worker = resolver._registry.register(
            provider="claude",
            models=["claude-sonnet-4-6"],
            worker_id=worker_id,
        )
        worker.status = "busy"
        worker.current_task_id = "auth"
        worker.current_run_id = "run_abc"
        resolver._graphs["run_abc"].nodes["auth"].status = "running"
        drain_response = client.post(f"/workers/{worker_id}/drain")
        assert drain_response.status_code == 200

        response = client.post(
            f"/workers/{worker_id}/report",
            json={
                "taskId": "auth",
                "attemptId": "att_drain",
                "status": "succeeded",
                "durationSeconds": 42.0,
            },
        )

        assert response.status_code == 200
        assert resolver._registry.get(worker_id).status == "draining"
        result_artifact = runtime_dir / "run_abc" / "results" / "auth.json"
        assert result_artifact.exists()
        assert '"attempt_id": "att_drain"' in result_artifact.read_text(encoding="utf-8")
        detail = client.get(f"/workers/{worker_id}")
        assert detail.status_code == 200
        assert detail.json()["status"] == "draining"


# ---- Get single worker ----


def test_get_worker_detail() -> None:
    with _worker_client() as client:
        worker_id = _register_worker(client)
        response = client.get(f"/workers/{worker_id}")
        assert response.status_code == 200
        detail = response.json()
        assert detail["workerId"] == worker_id
        assert detail["workerType"] == "pi_shell"
        assert detail["provider"] == "claude"
        assert detail["readinessReason"] is None
        assert detail["sessionStatus"] == "absent"
        assert detail["sessionStartedAt"] is None
        assert detail["sessionLastUsedAt"] is None
        assert detail["sessionFailureReason"] is None
        assert detail["sessionResetAvailable"] is True


def test_get_worker_detail_includes_readiness_reason_for_auth_expired() -> None:
    with _worker_client() as client:
        worker_id = _register_worker(client)
        engine = client.app.dependency_overrides[get_services]().sqlite_engine
        with Session(engine) as session:
            row = session.get(WorkerRegistryRecord, worker_id)
            assert row is not None
            row.status = "auth_expired"
            session.commit()

        response = client.get(f"/workers/{worker_id}")

        assert response.status_code == 200
        detail = response.json()
        assert detail["status"] == "auth_expired"
        assert detail["readinessReason"] == "Worker auth has expired and must be refreshed."


def test_get_unknown_worker_returns_404() -> None:
    with _worker_client() as client:
        response = client.get("/workers/wkr_nonexistent")
        assert response.status_code == 404


def test_pull_dispatch_returns_envelope_for_ready_task(tmp_path: Path) -> None:
    with _worker_client() as client:
        worker_id = _register_worker(client)
        resolver = _make_resolver()
        client.app.state.resolver = resolver
        client.app.state.worker_registry = resolver._registry
        client.app.state.settings = type(
            "SettingsStub",
            (),
            {"runtime_dir": tmp_path / ".oats" / "runtime"},
        )()

        worker = resolver._registry.register(
            provider="claude",
            models=["claude-sonnet-4-6"],
            worker_id=worker_id,
        )
        worker.status = "idle"

        response = client.get(f"/workers/{worker_id}/next-task")

        assert response.status_code == 200
        payload = response.json()
        assert payload["taskId"] == "auth"
        assert payload["attackPlan"]["objective"] is not None
        assert payload["sessionId"].startswith("sess_")


def test_pull_dispatch_returns_204_when_no_tasks(tmp_path: Path) -> None:
    with _worker_client() as client:
        worker_id = _register_worker(client)
        resolver = ResolverLoop(registry=InMemoryWorkerRegistry())
        client.app.state.resolver = resolver
        client.app.state.worker_registry = resolver._registry
        client.app.state.settings = type(
            "SettingsStub",
            (),
            {"runtime_dir": tmp_path / ".oats" / "runtime"},
        )()

        resolver._registry.register(
            provider="claude",
            models=["claude-sonnet-4-6"],
            worker_id=worker_id,
        )

        response = client.get(f"/workers/{worker_id}/next-task")

        assert response.status_code == 204


def test_report_result_completes_task(tmp_path: Path) -> None:
    with _worker_client() as client:
        worker_id = _register_worker(client)
        resolver = _make_resolver()
        client.app.state.resolver = resolver
        client.app.state.worker_registry = resolver._registry
        runtime_dir = tmp_path / ".oats" / "runtime"
        client.app.state.settings = type(
            "SettingsStub",
            (),
            {"runtime_dir": runtime_dir},
        )()

        worker = resolver._registry.register(
            provider="claude",
            models=["claude-sonnet-4-6"],
            worker_id=worker_id,
        )
        worker.status = "busy"
        worker.current_task_id = "auth"
        worker.current_run_id = "run_abc"
        resolver._graphs["run_abc"].nodes["auth"].status = "running"

        response = client.post(
            f"/workers/{worker_id}/report",
            json={
                "taskId": "auth",
                "attemptId": "att_test",
                "status": "succeeded",
                "durationSeconds": 120.0,
                "branchName": "oats/task/auth",
                "commitSha": "abc123",
            },
        )

        assert response.status_code == 200
        result_path = runtime_dir / "run_abc" / "results" / "auth" / "att_test.json"
        assert result_path.exists()
        assert resolver._completion_queue[0].task_id == "auth"
