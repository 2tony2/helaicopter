"""Endpoint tests for the database status and refresh API."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Callable, Iterator

from fastapi.testclient import TestClient

from helaicopter_api.application import database as database_application
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
                "tables": [],
            },
            "legacyDuckdb": {
                "key": "legacy_duckdb",
                "label": "Legacy DuckDB Snapshot",
                "engine": "DuckDB",
                "role": "legacy_debug",
                "availability": "missing",
                "note": "Legacy compatibility",
                "error": None,
                "path": "/tmp/helaicopter_olap.duckdb",
                "target": None,
                "publicPath": "/database-artifacts/olap/helaicopter_olap.duckdb",
                "docsUrl": "/database-schemas/olap/index.html",
                "tableCount": 0,
                "tables": [],
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


@contextmanager
def database_client(
    *,
    load_status: Callable[[], dict[str, object] | None],
    run_refresh: Callable[..., dict[str, object]],
) -> Iterator[tuple[TestClient, SimpleNamespace]]:
    application = create_app()
    services = SimpleNamespace(cache=StubCache(), sqlite_engine=StubEngine())
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
        assert body["databases"]["legacyDuckdb"]["key"] == "legacy_duckdb"
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
        assert body["databases"]["legacyDuckdb"]["key"] == "legacy_duckdb"
        assert services.cache.clear_calls == 1
        assert services.sqlite_engine.dispose_calls == 1
