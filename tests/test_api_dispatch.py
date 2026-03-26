"""Endpoint tests for dispatch queue monitoring and history."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from helaicopter_api.application.auth import create_credential
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.application.dispatch import InMemoryWorkerRegistry
from helaicopter_api.application.resolver import ResolverLoop
from helaicopter_api.schema.auth import CreateCredentialRequest
from helaicopter_api.server.config import Settings
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app
from helaicopter_db.models.oltp import OltpBase
from oats.graph import TaskGraph, TaskKind, TaskNode


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


@contextmanager
def _dispatch_client() -> Iterator[TestClient]:
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


def _task(task_id: str, title: str) -> TaskNode:
    return TaskNode(
        task_id=task_id,
        kind=TaskKind.IMPLEMENTATION,
        title=title,
        acceptance_criteria=["Tests pass"],
    )


def _set_runtime_dir(client: TestClient, tmp_path: Path) -> None:
    client.app.state.settings = type(
        "SettingsStub",
        (),
        {"runtime_dir": tmp_path / ".oats" / "runtime"},
    )()


def _run(coro):  # noqa: ANN001, ANN202
    return asyncio.run(coro)


def test_queue_snapshot_shows_ready_and_deferred(tmp_path: Path) -> None:
    with _dispatch_client() as client:
        graph = TaskGraph()
        graph.add_node(_task("ready-task", "Ready Task"))
        graph.add_node(_task("deferred-task", "Deferred Task"))

        resolver = ResolverLoop(
            registry=InMemoryWorkerRegistry(),
            graphs={"run_abc": graph},
            task_agents={
                "ready-task": "claude",
                "deferred-task": "codex",
            },
            task_models={
                "ready-task": "claude-sonnet-4-6",
                "deferred-task": "o3-pro",
            },
        )
        resolver._registry.register(
            provider="claude",
            models=["claude-sonnet-4-6"],
            worker_id="wkr_claude",
        )
        client.app.state.resolver = resolver
        _set_runtime_dir(client, tmp_path)

        response = client.get("/dispatch/queue")

        assert response.status_code == 200
        payload = response.json()
        assert [entry["taskId"] for entry in payload["ready"]] == ["ready-task"]
        assert len(payload["deferred"]) == 1
        assert payload["deferred"][0]["taskId"] == "deferred-task"
        assert payload["deferred"][0]["reason"] == "no_registered_worker"
        assert payload["deferred"][0]["reasonLabel"] == "No workers are registered for this provider."


def test_queue_snapshot_prefers_node_metadata_and_surfaces_auth_expired_reason(tmp_path: Path) -> None:
    with _dispatch_client() as client:
        graph = TaskGraph()
        graph.add_node(_task("deferred-task", "Deferred Task"))
        node = graph.get_node("deferred-task")
        node.agent = "codex"
        node.model = "o3-pro"

        resolver = ResolverLoop(
            registry=InMemoryWorkerRegistry(),
            graphs={"run_abc": graph},
            task_agents={"deferred-task": "claude"},
            task_models={"deferred-task": "claude-sonnet-4-6"},
        )
        resolver._registry.register(
            provider="codex",
            models=["o3-pro"],
            worker_id="wkr_codex",
            auth_status="expired",
        )
        client.app.state.resolver = resolver
        _set_runtime_dir(client, tmp_path)

        response = client.get("/dispatch/queue")

        assert response.status_code == 200
        payload = response.json()
        assert payload["ready"] == []
        assert payload["deferred"] == [
            {
                "runId": "run_abc",
                "taskId": "deferred-task",
                "provider": "codex",
                "model": "o3-pro",
                "reason": "auth_expired",
                "reasonLabel": "A matching worker exists, but its provider auth must be refreshed.",
            }
        ]


def test_queue_snapshot_reports_provider_not_ready_when_worker_exists_but_provider_auth_is_not_runnable(
    tmp_path: Path,
) -> None:
    with _dispatch_client() as client:
        engine = client.app.dependency_overrides[get_services]().sqlite_engine
        create_credential(
            engine,
            CreateCredentialRequest.model_validate(
                {
                    "provider": "codex",
                    "credentialType": "local_cli_session",
                }
            ),
        )

        graph = TaskGraph()
        graph.add_node(_task("codex-task", "Codex Task"))
        node = graph.get_node("codex-task")
        node.agent = "codex"
        node.model = "o3-pro"

        resolver = ResolverLoop(
            registry=InMemoryWorkerRegistry(),
            graphs={"run_provider": graph},
            task_agents={"codex-task": "codex"},
            task_models={"codex-task": "o3-pro"},
            sqlite_engine=engine,
        )
        resolver._registry.register(
            provider="codex",
            models=["o3-pro"],
            worker_id="wkr_codex_ready",
        )
        client.app.state.resolver = resolver
        _set_runtime_dir(client, tmp_path)

        response = client.get("/dispatch/queue")

        assert response.status_code == 200
        assert response.json()["deferred"] == [
            {
                "runId": "run_provider",
                "taskId": "codex-task",
                "provider": "codex",
                "model": "o3-pro",
                "reason": "provider_not_ready",
                "reasonLabel": "Provider auth or local session is not ready for execution.",
                "canRetry": False,
            }
        ]


def test_queue_snapshot_reports_worker_interrupted_as_retryable(tmp_path: Path) -> None:
    with _dispatch_client() as client:
        graph = TaskGraph()
        graph.add_node(_task("retry-task", "Retry Task"))
        node = graph.get_node("retry-task")
        node.agent = "claude"
        node.model = "claude-sonnet-4-6"
        node.status = "running"

        resolver = ResolverLoop(
            registry=InMemoryWorkerRegistry(),
            graphs={"run_retry": graph},
            task_agents={"retry-task": "claude"},
            task_models={"retry-task": "claude-sonnet-4-6"},
        )
        worker = resolver._registry.register(
            provider="claude",
            models=["claude-sonnet-4-6"],
            worker_id="wkr_interrupted",
        )
        worker.status = "busy"
        worker.current_task_id = "retry-task"
        worker.current_run_id = "run_retry"
        worker.last_heartbeat_at = worker.last_heartbeat_at.replace(year=2020)
        client.app.state.resolver = resolver
        _set_runtime_dir(client, tmp_path)

        _run(resolver.tick())
        response = client.get("/dispatch/queue")

        assert response.status_code == 200
        assert response.json()["deferred"] == [
            {
                "runId": "run_retry",
                "taskId": "retry-task",
                "provider": "claude",
                "model": "claude-sonnet-4-6",
                "reason": "worker_interrupted",
                "reasonLabel": "A worker disappeared mid-task; retry or re-route this work once capacity returns.",
                "canRetry": True,
            }
        ]


def test_dispatch_history_shows_recent_dispatches(tmp_path: Path) -> None:
    with _dispatch_client() as client:
        graph = TaskGraph()
        graph.add_node(_task("auth", "Auth"))

        resolver = ResolverLoop(
            registry=InMemoryWorkerRegistry(),
            graphs={"run_hist": graph},
            task_agents={"auth": "claude"},
            task_models={"auth": "claude-sonnet-4-6"},
        )
        resolver._registry.register(
            provider="claude",
            models=["claude-sonnet-4-6"],
            worker_id="wkr_history",
        )
        client.app.state.resolver = resolver
        _set_runtime_dir(client, tmp_path)
        _run(resolver.tick())

        response = client.get("/dispatch/history?limit=10")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload["entries"]) > 0
        entry = payload["entries"][0]
        assert entry["taskId"] == "auth"
        assert entry["workerId"] == "wkr_history"
        assert entry["provider"] == "claude"
        assert entry["model"] == "claude-sonnet-4-6"
        assert "dispatchedAt" in entry


def test_lifespan_startup_keeps_drained_worker_out_of_ready_queue(tmp_path: Path) -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    OltpBase.metadata.create_all(engine)
    settings = Settings(project_root=tmp_path, oats_runtime_dir=tmp_path / ".oats" / "runtime")
    services = _services_stub(sqlite_engine=engine)

    with (
        patch("helaicopter_api.server.lifespan.Settings", return_value=settings),
        patch("helaicopter_api.server.lifespan.build_services", return_value=services),
        TestClient(create_app()) as client,
    ):
        register = client.post("/workers/register", json={
            "workerType": "pi_shell",
            "provider": "claude",
            "capabilities": {
                "provider": "claude",
                "models": ["claude-sonnet-4-6"],
                "maxConcurrentTasks": 1,
                "supportsDiscovery": True,
                "supportsResume": True,
                "tags": [],
            },
            "host": "local",
            "pid": 123,
        })
        worker_id = register.json()["workerId"]
        client.app.state.worker_registry.register(
            provider="claude",
            models=["claude-sonnet-4-6"],
            worker_id=worker_id,
        )

        graph = TaskGraph()
        graph.add_node(_task("startup-task", "Startup Task"))
        client.app.state.resolver.submit_graph("run_startup", graph)

        before = client.get("/dispatch/queue")
        assert before.status_code == 200
        assert before.json()["ready"][0]["taskId"] == "startup-task"

        drain = client.post(f"/workers/{worker_id}/drain")
        assert drain.status_code == 200

        after = client.get("/dispatch/queue")
        assert after.status_code == 200
        assert after.json()["ready"] == []
        assert after.json()["deferred"] == [
            {
                "runId": "run_startup",
                "taskId": "startup-task",
                "provider": "claude",
                "model": "claude-sonnet-4-6",
                "reason": "draining",
                "reasonLabel": "Matching workers are draining and cannot accept new tasks.",
            }
        ]

    engine.dispose()
