"""Endpoint tests for provider readiness surfaces."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from helaicopter_api.application.auth import create_credential
from helaicopter_api.application.dispatch import InMemoryWorkerRegistry
from helaicopter_api.application.resolver import ResolverLoop
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.schema.auth import CreateCredentialRequest
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app
from helaicopter_db.models.oltp import OltpBase


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


@contextmanager
def _provider_client() -> Iterator[TestClient]:
    application = create_app()
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    OltpBase.metadata.create_all(engine)
    registry = InMemoryWorkerRegistry()
    resolver = ResolverLoop(registry=registry, sqlite_engine=engine)
    application.dependency_overrides[get_services] = lambda: _services_stub(sqlite_engine=engine)
    application.state.resolver = resolver
    application.state.worker_registry = registry
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.dependency_overrides.clear()
        engine.dispose()


def test_workers_provider_index_includes_provider_readiness_metadata() -> None:
    with _provider_client() as client:
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
        client.post(
            "/workers/register",
            json={
                "workerType": "pi_shell",
                "provider": "claude",
                "capabilities": {
                    "provider": "claude",
                    "models": ["claude-sonnet-4-6"],
                    "maxConcurrentTasks": 1,
                    "supportsDiscovery": False,
                    "supportsResume": False,
                    "tags": [],
                },
                "host": "local",
                "pid": 123,
            },
        )

        response = client.get("/workers/providers")

        assert response.status_code == 200
        payload = response.json()
        assert payload[0]["provider"] == "claude"
        assert payload[0]["status"] == "ready"
        assert payload[0]["blockingReasons"] == []


def test_operator_bootstrap_provider_summaries_include_provider_readiness_status() -> None:
    with _provider_client() as client:
        engine = client.app.dependency_overrides[get_services]().sqlite_engine
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
        client.post(
            "/workers/register",
            json={
                "workerType": "pi_shell",
                "provider": "codex",
                "capabilities": {
                    "provider": "codex",
                    "models": ["o3-pro"],
                    "maxConcurrentTasks": 1,
                    "supportsDiscovery": False,
                    "supportsResume": False,
                    "tags": [],
                },
                "host": "local",
                "pid": 321,
            },
        )

        response = client.get("/operator/bootstrap")

        assert response.status_code == 200
        codex_summary = next(item for item in response.json()["providers"] if item["provider"] == "codex")
        assert codex_summary["status"] == "ready"
        assert codex_summary["blockingReasons"] == []
