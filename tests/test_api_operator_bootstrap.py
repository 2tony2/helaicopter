"""Endpoint tests for the operator bootstrap readiness API."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session

from helaicopter_api.application.auth import create_credential
from helaicopter_api.application.dispatch import InMemoryWorkerRegistry
from helaicopter_api.application.resolver import ResolverLoop
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.auth import CreateCredentialRequest
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app
from helaicopter_db.models.oltp import OltpBase, WorkerRegistryRecord


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


@contextmanager
def _operator_client() -> Iterator[TestClient]:
    application = create_app()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    OltpBase.metadata.create_all(engine)
    registry = InMemoryWorkerRegistry()
    resolver = ResolverLoop(registry=registry)

    application.dependency_overrides[get_services] = lambda: _services_stub(
        sqlite_engine=engine,
    )
    application.state.resolver = resolver
    application.state.worker_registry = registry
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.dependency_overrides.clear()
        engine.dispose()


def _register_worker(client: TestClient, *, provider: str) -> str:
    response = client.post(
        "/workers/register",
        json={
            "workerType": "pi_shell",
            "provider": provider,
            "capabilities": {
                "provider": provider,
                "models": ["claude-sonnet-4-6"] if provider == "claude" else ["o3-pro"],
                "maxConcurrentTasks": 1,
                "supportsDiscovery": False,
                "supportsResume": False,
                "tags": [],
            },
            "host": "local",
            "pid": 12345,
        },
    )
    assert response.status_code == 201
    return response.json()["workerId"]


def test_operator_bootstrap_reports_missing_workers() -> None:
    with _operator_client() as client:
        response = client.get("/operator/bootstrap")

        assert response.status_code == 200
        payload = response.json()
        assert payload["overallStatus"] == "blocked"
        reason_codes = [reason["code"] for reason in payload["blockingReasons"]]
        assert "no_registered_workers" in reason_codes
        no_workers_reason = next(
            reason for reason in payload["blockingReasons"] if reason["code"] == "no_registered_workers"
        )
        assert "Register a Claude worker and a Codex worker" in no_workers_reason["nextStep"]


def test_operator_bootstrap_reports_provider_gaps() -> None:
    with _operator_client() as client:
        _register_worker(client, provider="claude")

        response = client.get("/operator/bootstrap")

        assert response.status_code == 200
        payload = response.json()
        codes = [reason["code"] for reason in payload["blockingReasons"]]
        assert "missing_codex_worker" in codes


def test_operator_bootstrap_stays_blocked_when_provider_auth_is_missing() -> None:
    with _operator_client() as client:
        _register_worker(client, provider="claude")
        _register_worker(client, provider="codex")
        client.app.state.resolver._running = True

        response = client.get("/operator/bootstrap")

        assert response.status_code == 200
        payload = response.json()
        assert payload["overallStatus"] == "blocked"
        assert {provider["status"] for provider in payload["providers"]} == {"blocked"}


def test_operator_bootstrap_reports_ready_when_workers_and_credentials_exist() -> None:
    with _operator_client() as client:
        _register_worker(client, provider="claude")
        _register_worker(client, provider="codex")
        client.app.state.resolver._running = True
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
        assert payload["blockingReasons"] == []


def test_operator_bootstrap_reports_auth_expired_workers() -> None:
    with _operator_client() as client:
        worker_id = _register_worker(client, provider="claude")
        engine = client.app.dependency_overrides[get_services]().sqlite_engine
        with Session(engine) as session:
            row = session.get(WorkerRegistryRecord, worker_id)
            assert row is not None
            row.status = "auth_expired"
            session.commit()

        response = client.get("/operator/bootstrap")

        assert response.status_code == 200
        payload = response.json()
        assert "auth_expired_workers" in [reason["code"] for reason in payload["blockingReasons"]]
