"""Endpoint tests for the database status and refresh API."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator

from fastapi.testclient import TestClient

from helaicopter_api.application import database as database_application
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app


def _status_payload(
    *,
    status: str = "completed",
    trigger: str = "manual",
    error: str | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "trigger": trigger,
        "startedAt": "2026-03-17T10:00:00Z",
        "finishedAt": "2026-03-17T10:00:10Z",
        "durationMs": 10_000,
        "error": error,
        "lastSuccessfulRefreshAt": "2026-03-17T10:00:10Z",
        "idempotencyKey": "input-key-123",
        "scopeLabel": "Current export window",
        "windowDays": 7,
        "windowStart": "2026-03-10T00:00:00Z",
        "windowEnd": "2026-03-17T00:00:00Z",
        "sourceConversationCount": 42,
        "refreshIntervalMinutes": 360,
        "runtime": {
            "analyticsReadBackend": "legacy",
            "conversationSummaryReadBackend": "legacy",
        },
        "databases": {
            "sqlite": {
                "key": "sqlite",
                "label": "SQLite Metadata Store",
                "engine": "SQLite",
                "role": "metadata",
                "availability": "ready",
                "note": "App-local metadata",
                "error": None,
                "path": "/tmp/helaicopter_oltp.sqlite",
                "target": None,
                "publicPath": "/database-artifacts/oltp/helaicopter_oltp.sqlite",
                "docsUrl": "/database-schemas/oltp/index.html",
                "tableCount": 1,
                "tables": [
                    {
                        "name": "refresh_runs",
                        "rowCount": 1,
                        "columns": [],
                    }
                ],
            },
            "duckdb": {
                "key": "duckdb",
                "label": "DuckDB Inspection Snapshot",
                "engine": "DuckDB",
                "role": "inspection",
                "availability": "missing",
                "note": "DuckDB inspection snapshot",
                "error": None,
                "path": "/tmp/helaicopter_olap.duckdb",
                "target": None,
                "publicPath": "/database-artifacts/olap/helaicopter_olap.duckdb",
                "docsUrl": "/database-schemas/olap/index.html",
                "tableCount": 1,
                "tables": [
                    {
                        "name": "daily_conversation_metrics",
                        "rowCount": 7,
                        "columns": [],
                    }
                ],
            },
        },
    }


class StubCache:
    def __init__(self) -> None:
        self.clear_calls = 0

    def clear(self) -> None:
        self.clear_calls += 1


class StubEngine:
    def __init__(self) -> None:
        self.dispose_calls = 0

    def dispose(self) -> None:
        self.dispose_calls += 1


def _services_stub(**attrs: object) -> BackendServices:
    services = object.__new__(BackendServices)
    for name, value in attrs.items():
        setattr(services, name, value)
    return services


@contextmanager
def database_client(
    *,
    load_status: Callable[[], dict[str, object] | None],
    run_refresh: Callable[..., dict[str, object]],
) -> Iterator[tuple[TestClient, BackendServices]]:
    application = create_app()
    services = _services_stub(cache=StubCache(), sqlite_engine=StubEngine())
    application.dependency_overrides[get_services] = lambda: services
    original_load_status = database_application.load_status
    original_run_refresh = database_application.run_refresh
    database_application.load_status = load_status
    database_application.run_refresh = run_refresh
    try:
        with TestClient(application) as client:
            yield client, services
    finally:
        database_application.load_status = original_load_status
        database_application.run_refresh = original_run_refresh
        application.dependency_overrides.clear()


class TestDatabaseEndpoints:
    def test_status_endpoint_bootstraps_when_persisted_status_payload_is_malformed(self) -> None:
        refresh_calls: list[dict[str, object]] = []

        def run_refresh(**kwargs: object) -> dict[str, object]:
            refresh_calls.append(kwargs)
            return _status_payload(trigger="bootstrap")

        with database_client(load_status=lambda: [], run_refresh=run_refresh) as (client, services):
            response = client.get("/databases/status")

        assert response.status_code == 200
        assert response.json()["trigger"] == "bootstrap"
        assert refresh_calls == [
            {"force": True, "trigger": "bootstrap", "stale_after_seconds": 21_600},
        ]
        assert services.cache.clear_calls == 1
        assert services.sqlite_engine.dispose_calls == 1

    def test_status_endpoint_bootstraps_refresh_when_status_is_missing(self) -> None:
        refresh_calls: list[dict[str, object]] = []

        def run_refresh(**kwargs: object) -> dict[str, object]:
            refresh_calls.append(kwargs)
            return _status_payload(trigger="bootstrap")

        with database_client(load_status=lambda: None, run_refresh=run_refresh) as (client, services):
            response = client.get("/databases/status")

        assert response.status_code == 200
        assert response.json()["trigger"] == "bootstrap"
        assert refresh_calls == [
            {"force": True, "trigger": "bootstrap", "stale_after_seconds": 21_600},
        ]
        assert services.cache.clear_calls == 1
        assert services.sqlite_engine.dispose_calls == 1

    def test_refresh_endpoint_returns_status_and_invalidates_backend_caches(self) -> None:
        refresh_calls: list[dict[str, object]] = []

        def run_refresh(**kwargs: object) -> dict[str, object]:
            refresh_calls.append(kwargs)
            return _status_payload(trigger="manual-ui")

        with database_client(load_status=lambda: None, run_refresh=run_refresh) as (client, services):
            response = client.post(
                "/databases/refresh",
                json={"force": True, "trigger": "manual-ui", "staleAfterSeconds": 123},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert body["runtime"]["analyticsReadBackend"] == "legacy"
        assert body["databases"]["duckdb"]["key"] == "duckdb"
        assert "legacyDuckdb" not in body["databases"]
        assert body["databases"]["sqlite"]["tables"][0]["servingClass"] == "fastapi-derived"
        assert body["databases"]["sqlite"]["tables"][0]["integrationType"] == "sqlalchemy"
        assert body["databases"]["sqlite"]["tables"][0]["sqlalchemyModel"] == "RefreshRun"
        assert "/databases/status" in body["databases"]["sqlite"]["tables"][0]["fastapiRoutes"]
        assert body["databases"]["duckdb"]["tables"][0]["servingClass"] == "schema-inspection"
        assert body["databases"]["duckdb"]["tables"][0]["integrationType"] == "duckdb-inspection"
        assert refresh_calls == [
            {"force": True, "trigger": "manual-ui", "stale_after_seconds": 123},
        ]
        assert services.cache.clear_calls == 1
        assert services.sqlite_engine.dispose_calls == 1

    def test_refresh_endpoint_reports_failed_status_payload(self) -> None:
        def run_refresh(**_kwargs: object) -> dict[str, object]:
            raise RuntimeError("refresh exploded")

        failed_status = {
            "status": "failed",
            "trigger": "manual",
            "startedAt": "2026-03-17T10:00:00Z",
            "finishedAt": "2026-03-17T10:00:02Z",
            "durationMs": 2_000,
            "error": "refresh exploded",
            "scopeLabel": "Current export window",
            "windowDays": 7,
            "windowStart": "2026-03-10T00:00:00Z",
            "windowEnd": "2026-03-17T00:00:00Z",
            "sourceConversationCount": 42,
        }

        with database_client(load_status=lambda: failed_status, run_refresh=run_refresh) as (client, services):
            response = client.post("/databases/refresh", json={})

        assert response.status_code == 500
        body = response.json()
        assert body["status"] == "failed"
        assert body["error"] == "refresh exploded"
        assert body["runtime"]["conversationSummaryReadBackend"] == "legacy"
        assert body["databases"]["sqlite"]["key"] == "sqlite"
        assert body["databases"]["duckdb"]["key"] == "duckdb"
        assert services.cache.clear_calls == 1
        assert services.sqlite_engine.dispose_calls == 1

    def test_refresh_endpoint_rejects_snake_case_payload_keys(self) -> None:
        def run_refresh(**_kwargs: object) -> dict[str, object]:
            return _status_payload(trigger="manual-ui")

        with database_client(load_status=lambda: None, run_refresh=run_refresh) as (client, _services):
            response = client.post(
                "/databases/refresh",
                json={"force": True, "trigger": "manual-ui", "stale_after_seconds": 123},
            )

        assert response.status_code == 422
        assert any(error["loc"][-1] == "stale_after_seconds" for error in response.json()["detail"])

    def test_openapi_exposes_database_camel_case_contract_fragments(self) -> None:
        def run_refresh(**_kwargs: object) -> dict[str, object]:
            return _status_payload(trigger="manual-ui")

        with database_client(load_status=lambda: _status_payload(), run_refresh=run_refresh) as (client, _services):
            response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()
        refresh_post = schema["paths"]["/databases/refresh"]["post"]
        request_schema = schema["components"]["schemas"]["DatabaseRefreshRequest"]
        status_schema = schema["components"]["schemas"]["DatabaseStatusResponse"]
        table_schema = schema["components"]["schemas"]["DatabaseTableSchemaResponse"]

        assert refresh_post["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/DatabaseRefreshRequest"
        )
        assert "staleAfterSeconds" in request_schema["properties"]
        assert "stale_after_seconds" not in request_schema["properties"]
        assert "lastSuccessfulRefreshAt" in status_schema["properties"]
        assert "last_successful_refresh_at" not in status_schema["properties"]
        assert "duckdb" in schema["components"]["schemas"]["DatabaseArtifactsResponse"]["properties"]
        assert "legacyDuckdb" not in schema["components"]["schemas"]["DatabaseArtifactsResponse"]["properties"]
        assert "servingClass" in table_schema["properties"]
        assert "integrationType" in table_schema["properties"]
        assert "fastapiRoutes" in table_schema["properties"]
        assert "sqlalchemyModel" in table_schema["properties"]
