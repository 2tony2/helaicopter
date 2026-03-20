"""Endpoint tests for the database status and refresh API."""

from __future__ import annotations

import importlib
import importlib.util
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Callable, Iterator

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from helaicopter_api.application import database as database_application
from helaicopter_api.bootstrap.services import BackendServices
from helaicopter_api.server.config import Settings
from helaicopter_api.server.dependencies import get_services
from helaicopter_api.server.main import create_app
from helaicopter_db import refresh as refresh_module
from helaicopter_db.export_pipeline import ExportMeta
from helaicopter_db.models import ConversationRecord, FactConversation, OlapBase, OltpBase


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
            "analyticsReadBackend": "duckdb",
            "conversationSummaryReadBackend": "legacy",
        },
        "databases": {
            "frontendCache": {
                "key": "frontend_cache",
                "label": "Frontend Short-Term Cache",
                "engine": "In-process memory",
                "role": "cache",
                "availability": "ready",
                "health": "healthy",
                "operationalStatus": "Warm in-process response cache",
                "note": "Short-lived backend read cache for dashboard and conversation views.",
                "error": None,
                "path": None,
                "target": "BackendServices.cache",
                "tableCount": 0,
                "tables": [],
                "sizeBytes": 64,
                "sizeDisplay": "64 B",
                "inventorySummary": "1 cached key",
                "load": [],
            },
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
            "prefectPostgres": {
                "key": "prefect_postgres",
                "label": "Prefect Postgres",
                "engine": "Postgres",
                "role": "orchestration",
                "availability": "ready",
                "health": "healthy",
                "operationalStatus": "Prefect API responding",
                "note": "Backing store for the local Prefect control plane.",
                "error": None,
                "path": None,
                "target": "postgresql://prefect@127.0.0.1:5432/prefect",
                "publicPath": None,
                "docsUrl": None,
                "tableCount": 0,
                "tables": [],
            },
        },
    }


class StubCache:
    def __init__(self) -> None:
        self.clear_calls = 0
        self.deleted_keys: list[str] = []
        self.values: dict[str, object] = {}

    def clear(self) -> None:
        self.clear_calls += 1

    def delete(self, key: str) -> None:
        self.deleted_keys.append(key)
        self.values.pop(key, None)

    def set(self, key: str, value: object) -> None:
        self.values[key] = value

    def get(self, key: str, default: object | None = None) -> object | None:
        return self.values.get(key, default)


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
        assert services.cache.clear_calls == 0
        assert services.cache.deleted_keys == [
            "analytics",
            "codex_session_artifacts",
            "codex_threads_by_id",
            "database_status",
            "projects",
        ]
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
        assert services.cache.clear_calls == 0
        assert services.cache.deleted_keys == [
            "analytics",
            "codex_session_artifacts",
            "codex_threads_by_id",
            "database_status",
            "projects",
        ]
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
        assert body["runtime"]["analyticsReadBackend"] == "duckdb"
        assert body["databases"]["frontendCache"]["key"] == "frontend_cache"
        assert body["databases"]["duckdb"]["key"] == "duckdb"
        assert body["databases"]["prefectPostgres"]["key"] == "prefect_postgres"
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
        assert services.cache.clear_calls == 0
        assert services.cache.deleted_keys == [
            "analytics",
            "codex_session_artifacts",
            "codex_threads_by_id",
            "database_status",
            "projects",
        ]
        assert services.sqlite_engine.dispose_calls == 1

    def test_refresh_endpoint_preserves_unrelated_cache_entries(self) -> None:
        def run_refresh(**kwargs: object) -> dict[str, object]:
            assert kwargs == {"force": True, "trigger": "manual-ui", "stale_after_seconds": 123}
            return _status_payload(trigger="manual-ui")

        with database_client(load_status=lambda: None, run_refresh=run_refresh) as (client, services):
            services.cache.set("analytics", {"stale": True})
            services.cache.set("codex_session_artifacts", ["stale"])
            services.cache.set("database_status", {"stale": True})
            services.cache.set("keep-me", {"fresh": True})

            response = client.post(
                "/databases/refresh",
                json={"force": True, "trigger": "manual-ui", "staleAfterSeconds": 123},
            )

        assert response.status_code == 200
        assert services.cache.get("keep-me") == {"fresh": True}
        assert services.cache.get("analytics") is None
        assert services.cache.get("codex_session_artifacts") is None
        assert services.cache.get("database_status") is None
        assert services.cache.clear_calls == 0

    def test_refresh_endpoint_accepts_full_rebuild_requests(self) -> None:
        refresh_calls: list[dict[str, object]] = []

        def run_refresh(**kwargs: object) -> dict[str, object]:
            refresh_calls.append(kwargs)
            return _status_payload(trigger="manual-full-rebuild")

        with database_client(load_status=lambda: None, run_refresh=run_refresh) as (client, _services):
            response = client.post(
                "/databases/refresh",
                json={
                    "fullRebuild": True,
                    "trigger": "manual-full-rebuild",
                    "staleAfterSeconds": 0,
                },
            )

        assert response.status_code == 200
        assert response.json()["trigger"] == "manual-full-rebuild"
        assert refresh_calls == [
            {
                "force": True,
                "full_rebuild": True,
                "trigger": "manual-full-rebuild",
                "stale_after_seconds": 0,
            }
        ]

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
        assert body["databases"]["frontendCache"]["key"] == "frontend_cache"
        assert body["databases"]["sqlite"]["key"] == "sqlite"
        assert body["databases"]["duckdb"]["key"] == "duckdb"
        assert body["databases"]["prefectPostgres"]["key"] == "prefect_postgres"
        assert services.cache.clear_calls == 0
        assert services.cache.deleted_keys == [
            "analytics",
            "codex_session_artifacts",
            "codex_threads_by_id",
            "database_status",
            "projects",
        ]
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
        assert "frontendCache" in schema["components"]["schemas"]["DatabaseArtifactsResponse"]["properties"]
        assert "duckdb" in schema["components"]["schemas"]["DatabaseArtifactsResponse"]["properties"]
        assert "prefectPostgres" in schema["components"]["schemas"]["DatabaseArtifactsResponse"]["properties"]
        assert "legacyDuckdb" not in schema["components"]["schemas"]["DatabaseArtifactsResponse"]["properties"]
        assert "servingClass" in table_schema["properties"]
        assert "integrationType" in table_schema["properties"]
        assert "fastapiRoutes" in table_schema["properties"]
        assert "sqlalchemyModel" in table_schema["properties"]


def _test_settings(tmp_path: Path) -> Settings:
    return Settings(
        project_root=tmp_path,
        claude_dir=tmp_path / ".claude",
        codex_dir=tmp_path / ".codex",
    )


def _conversation_envelope(
    *,
    session_id: str,
    first_message: str,
    ended_at_ms: int,
    source_file_modified_at_ms: int,
) -> dict[str, object]:
    return {
        "type": "conversation",
        "summary": {
            "sessionId": session_id,
            "projectPath": "-Users-tony-Code-helaicopter",
            "projectName": "Code/helaicopter",
            "threadType": "main",
            "firstMessage": first_message,
            "timestamp": 1_763_200_000_000,
            "messageCount": 1,
            "model": "claude-sonnet-4-5",
            "gitBranch": "main",
            "speed": "standard",
            "totalInputTokens": 10,
            "totalOutputTokens": 5,
            "totalCacheCreationTokens": 0,
            "totalCacheReadTokens": 0,
            "totalReasoningTokens": 0,
            "toolUseCount": 0,
            "subagentCount": 0,
            "taskCount": 0,
            "toolBreakdown": {},
            "subagentTypeBreakdown": {},
            "recordSource": f"/tmp/{session_id}.jsonl",
            "sourceFileModifiedAt": source_file_modified_at_ms,
        },
        "detail": {
            "endTime": ended_at_ms,
            "messages": [
                {
                    "role": "assistant",
                    "timestamp": ended_at_ms,
                    "model": "claude-sonnet-4-5",
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 5,
                    },
                    "blocks": [{"type": "text", "text": first_message}],
                }
            ],
            "plans": [],
            "subagents": [],
            "contextAnalytics": {"buckets": [], "steps": []},
        },
        "tasks": [],
        "cost": {
            "inputCost": 0.1,
            "outputCost": 0.2,
            "cacheWriteCost": 0.0,
            "cacheReadCost": 0.0,
            "totalCost": 0.3,
        },
    }


def _derive_route_slug(first_message: str) -> str:
    conversation_refs = importlib.import_module("helaicopter_api.application.conversation_refs")
    return conversation_refs.derive_route_slug(first_message)


def _load_route_slug_migration():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "python"
        / "alembic"
        / "versions"
        / "20260320_0010_conversation_route_refs.py"
    )
    spec = importlib.util.spec_from_file_location("test_conversation_route_refs_migration", migration_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_pre_route_slug_conversations_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE conversations (
          conversation_id TEXT PRIMARY KEY,
          provider TEXT NOT NULL,
          session_id TEXT NOT NULL,
          project_path TEXT NOT NULL,
          project_name TEXT NOT NULL,
          thread_type TEXT NOT NULL,
          first_message TEXT NOT NULL,
          started_at TEXT NOT NULL,
          ended_at TEXT NOT NULL,
          message_count INTEGER NOT NULL,
          model TEXT,
          git_branch TEXT,
          reasoning_effort TEXT,
          speed TEXT,
          total_input_tokens INTEGER NOT NULL,
          total_output_tokens INTEGER NOT NULL,
          total_cache_write_tokens INTEGER NOT NULL,
          total_cache_read_tokens INTEGER NOT NULL,
          total_reasoning_tokens INTEGER NOT NULL,
          tool_use_count INTEGER NOT NULL,
          subagent_count INTEGER NOT NULL,
          task_count INTEGER NOT NULL,
          estimated_input_cost TEXT,
          estimated_output_cost TEXT,
          estimated_cache_write_cost TEXT,
          estimated_cache_read_cost TEXT,
          estimated_total_cost TEXT,
          record_source TEXT,
          source_file_modified_at TEXT,
          loaded_at TEXT NOT NULL,
          first_ingested_at TEXT NOT NULL,
          last_refreshed_at TEXT NOT NULL
        )
        """
    )


def _insert_pre_route_slug_conversation(connection: sqlite3.Connection, *, conversation_id: str, first_message: str) -> None:
    connection.execute(
        """
        INSERT INTO conversations (
          conversation_id,
          provider,
          session_id,
          project_path,
          project_name,
          thread_type,
          first_message,
          started_at,
          ended_at,
          message_count,
          model,
          git_branch,
          reasoning_effort,
          speed,
          total_input_tokens,
          total_output_tokens,
          total_cache_write_tokens,
          total_cache_read_tokens,
          total_reasoning_tokens,
          tool_use_count,
          subagent_count,
          task_count,
          estimated_input_cost,
          estimated_output_cost,
          estimated_cache_write_cost,
          estimated_cache_read_cost,
          estimated_total_cost,
          record_source,
          source_file_modified_at,
          loaded_at,
          first_ingested_at,
          last_refreshed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            "claude",
            conversation_id.removeprefix("claude:"),
            "-Users-tony-Code-helaicopter",
            "helaicopter",
            "main",
            first_message,
            "2026-03-10T09:00:00+00:00",
            "2026-03-10T09:05:00+00:00",
            1,
            "claude-sonnet-4-5",
            "main",
            None,
            "standard",
            10,
            5,
            0,
            0,
            0,
            0,
            0,
            0,
            "0.1",
            "0.2",
            "0.0",
            "0.0",
            "0.3",
            "/tmp/source.jsonl",
            None,
            "2026-03-10T09:05:00+00:00",
            "2026-03-10T09:05:00+00:00",
            "2026-03-10T09:05:00+00:00",
        ),
    )


def _upgrade_route_slug_migration(db_path: Path) -> None:
    migration = _load_route_slug_migration()
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        with engine.begin() as connection:
            operations = Operations(MigrationContext.configure(connection))
            original_op = migration.op
            migration.op = operations
            try:
                migration.upgrade_oltp()
            finally:
                migration.op = original_op
    finally:
        engine.dispose()


class TestConversationRouteSlugMigration:
    def test_route_slug_migration_adds_and_backfills_stored_slug_column(self, tmp_path: Path) -> None:
        db_path = tmp_path / "migration.sqlite"
        try:
            connection = sqlite3.connect(db_path)
            _create_pre_route_slug_conversations_table(connection)
            _insert_pre_route_slug_conversation(
                connection,
                conversation_id="claude:session-stored",
                first_message="Review the backend rollout",
            )
            connection.commit()
            connection.close()

            _upgrade_route_slug_migration(db_path)

            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row

            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(conversations)").fetchall()
            }
            row = connection.execute(
                "SELECT route_slug FROM conversations WHERE conversation_id = ?",
                ("claude:session-stored",),
            ).fetchone()
        finally:
            connection.close()

        assert "route_slug" in columns
        assert row is not None
        assert row["route_slug"] == "review-the-backend-rollout"

    def test_route_slug_migration_backfill_matches_shared_slug_derivation_for_edge_cases(
        self,
        tmp_path: Path,
    ) -> None:
        db_path = tmp_path / "migration.sqlite"
        try:
            connection = sqlite3.connect(db_path)
            _create_pre_route_slug_conversations_table(connection)
            first_messages = {
                "claude:session-punctuation": "  Review!!!   the---backend rollout??  ",
                "claude:session-trim": "A" * 120,
                "claude:session-ascii": "Crème brûlée für jalapeño",
                "claude:session-default": "東京!!!",
            }
            for conversation_id, first_message in first_messages.items():
                _insert_pre_route_slug_conversation(
                    connection,
                    conversation_id=conversation_id,
                    first_message=first_message,
                )

            connection.commit()
            connection.close()

            _upgrade_route_slug_migration(db_path)

            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row

            rows = connection.execute(
                "SELECT conversation_id, first_message, route_slug FROM conversations ORDER BY conversation_id ASC"
            ).fetchall()
        finally:
            connection.close()

        route_slugs = {row["conversation_id"]: row["route_slug"] for row in rows}
        assert route_slugs == {
            conversation_id: _derive_route_slug(first_message)
            for conversation_id, first_message in first_messages.items()
        }
        assert route_slugs["claude:session-punctuation"] == "review-the-backend-rollout"
        assert route_slugs["claude:session-trim"] == "a" * 80
        assert route_slugs["claude:session-ascii"] == "creme-brulee-fur-jalapeno"
        assert route_slugs["claude:session-default"] == "conversation"

    def test_route_slug_migration_enforces_not_null_column(self, tmp_path: Path) -> None:
        db_path = tmp_path / "migration.sqlite"
        try:
            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row
            _create_pre_route_slug_conversations_table(connection)
            _insert_pre_route_slug_conversation(
                connection,
                conversation_id="claude:session-not-null",
                first_message="Persist the invariant",
            )
            connection.commit()
            connection.close()

            _upgrade_route_slug_migration(db_path)

            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row
            route_slug_column = next(
                row
                for row in connection.execute("PRAGMA table_info(conversations)").fetchall()
                if row["name"] == "route_slug"
            )
        finally:
            connection.close()

        assert route_slug_column["notnull"] == 1

    def test_route_slug_migration_enforces_not_null_column_on_empty_tables(self, tmp_path: Path) -> None:
        db_path = tmp_path / "migration.sqlite"
        try:
            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row
            _create_pre_route_slug_conversations_table(connection)
            connection.commit()
            connection.close()

            _upgrade_route_slug_migration(db_path)

            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row
            route_slug_column = next(
                row
                for row in connection.execute("PRAGMA table_info(conversations)").fetchall()
                if row["name"] == "route_slug"
            )
        finally:
            connection.close()

        assert route_slug_column["notnull"] == 1


class TestRefreshOperationalStore:
    def test_run_refresh_upserts_conversations_and_reconciles_removed_rows(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        settings = _test_settings(tmp_path)
        olap_engine = create_engine(f"sqlite:///{tmp_path / 'olap.sqlite'}", future=True)
        payloads = [
            {
                "meta": {
                    "conversation_count": 2,
                    "input_key": "window-1",
                    "scope_label": "Historical window",
                    "window_days": 365,
                    "window_start": "2025-03-19T00:00:00+00:00",
                    "window_end": "2026-03-19T00:00:00+00:00",
                },
                "rows": [
                    _conversation_envelope(
                        session_id="session-a",
                        first_message="First revision",
                        ended_at_ms=1_763_200_010_000,
                        source_file_modified_at_ms=1_763_200_020_000,
                    ),
                    _conversation_envelope(
                        session_id="session-b",
                        first_message="To be removed",
                        ended_at_ms=1_763_200_030_000,
                        source_file_modified_at_ms=1_763_200_040_000,
                    ),
                ],
            },
            {
                "meta": {
                    "conversation_count": 1,
                    "input_key": "window-2",
                    "scope_label": "Historical window",
                    "window_days": 365,
                    "window_start": "2025-03-19T00:00:00+00:00",
                    "window_end": "2026-03-19T00:00:00+00:00",
                },
                "rows": [
                    _conversation_envelope(
                        session_id="session-a",
                        first_message="Second revision",
                        ended_at_ms=1_763_200_050_000,
                        source_file_modified_at_ms=1_763_200_060_000,
                    )
                ],
            },
        ]
        current = {"index": 0}

        def fake_meta(_settings: Settings | None = None) -> refresh_module.ExportMeta:
            raw = payloads[current["index"]]["meta"]
            return refresh_module.ExportMeta(
                conversation_count=raw["conversation_count"],
                input_key=raw["input_key"],
                scope_label=raw["scope_label"],
                window_days=raw["window_days"],
                window_start=raw["window_start"],
                window_end=raw["window_end"],
            )

        def fake_rows(_settings: Settings | None = None):
            yield from payloads[current["index"]]["rows"]

        def fake_run_migrations(target: str, settings_arg: Settings | None = None) -> None:
            if target == "oltp":
                engine = refresh_module.create_oltp_engine(settings_arg or settings)
                try:
                    OltpBase.metadata.create_all(engine)
                finally:
                    engine.dispose()
                return
            OlapBase.metadata.create_all(olap_engine)

        monkeypatch.setattr(refresh_module, "read_export_meta", fake_meta)
        monkeypatch.setattr(refresh_module, "iter_export_rows", fake_rows)
        monkeypatch.setattr(refresh_module, "_run_migrations", fake_run_migrations)
        monkeypatch.setattr(refresh_module, "create_olap_engine", lambda _settings=None: olap_engine)
        monkeypatch.setattr(refresh_module, "generate_schema_docs", lambda _settings=None: None)

        refresh_module.run_refresh(force=True, trigger="test", stale_after_seconds=0, settings=settings)
        with Session(refresh_module.create_oltp_engine(settings)) as session:
            original = session.get(ConversationRecord, "claude:session-a")
        assert original is not None
        assert original.route_slug == _derive_route_slug("First revision")

        current["index"] = 1
        refresh_module.run_refresh(force=False, trigger="test", stale_after_seconds=0, settings=settings)

        with Session(refresh_module.create_oltp_engine(settings)) as session:
            conversations = session.scalars(
                select(ConversationRecord).order_by(ConversationRecord.session_id.asc())
            ).all()

        assert [conversation.session_id for conversation in conversations] == ["session-a"]
        updated = conversations[0]
        assert updated.first_message == "Second revision"
        assert updated.route_slug == _derive_route_slug("First revision")
        assert updated.ended_at.isoformat().startswith("2025-11-15T09:47:30")
        assert updated.source_file_modified_at is not None
        assert updated.source_file_modified_at.isoformat().startswith("2025-11-15T09:47:40")
        assert updated.record_source == "/tmp/session-a.jsonl"
        assert updated.loaded_at == updated.last_refreshed_at
        assert updated.first_ingested_at < updated.last_refreshed_at

        connection = sqlite3.connect(settings.app_sqlite_path)
        try:
            message_count = connection.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0]
            removed = connection.execute(
                "SELECT COUNT(*) FROM conversations WHERE session_id = ?",
                ("session-b",),
            ).fetchone()[0]
        finally:
            connection.close()

        assert message_count == 1
        assert removed == 0


def _export_envelope(
    session_id: str,
    *,
    timestamp_ms: int,
    total_input_tokens: int,
) -> dict[str, object]:
    return {
        "type": "conversation",
        "summary": {
            "sessionId": session_id,
            "projectPath": "-Users-tony-Code-helaicopter",
            "projectName": "helaicopter",
            "threadType": "main",
            "firstMessage": f"session {session_id}",
            "timestamp": timestamp_ms,
            "messageCount": 1,
            "model": "claude-sonnet-4-5-20250929",
            "totalInputTokens": total_input_tokens,
            "totalOutputTokens": 0,
            "totalCacheCreationTokens": 0,
            "totalCacheReadTokens": 0,
            "totalReasoningTokens": 0,
            "toolUseCount": 0,
            "subagentCount": 0,
            "taskCount": 0,
            "toolBreakdown": {},
            "subagentTypeBreakdown": {},
        },
        "detail": {
            "endTime": timestamp_ms + 60_000,
            "messages": [
                {
                    "role": "assistant",
                    "timestamp": timestamp_ms,
                    "model": "claude-sonnet-4-5-20250929",
                    "usage": {
                        "input_tokens": total_input_tokens,
                        "output_tokens": 0,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0,
                    },
                    "blocks": [{"type": "text", "text": f"session {session_id} body"}],
                }
            ],
            "plans": [],
            "subagents": [],
            "contextAnalytics": {"buckets": [], "steps": []},
        },
        "tasks": [],
        "cost": {
            "inputCost": 0.0,
            "outputCost": 0.0,
            "cacheWriteCost": 0.0,
            "cacheReadCost": 0.0,
            "totalCost": 0.0,
        },
    }


@pytest.fixture
def refresh_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path):
    settings = Settings(project_root=tmp_path)
    oltp_engine = create_engine(f"sqlite:///{tmp_path / 'oltp.sqlite'}", future=True)
    olap_engine = create_engine(f"sqlite:///{tmp_path / 'olap.sqlite'}", future=True)
    OltpBase.metadata.create_all(oltp_engine)
    OlapBase.metadata.create_all(olap_engine)

    meta = ExportMeta(
        conversation_count=0,
        input_key="input-key-123",
        scope_label="Current export window",
        window_days=7,
        window_start="2026-03-10T00:00:00Z",
        window_end="2026-03-17T00:00:00Z",
    )
    envelopes: list[dict[str, object]] = []

    monkeypatch.setattr(refresh_module, "create_oltp_engine", lambda _settings=None: oltp_engine)
    monkeypatch.setattr(refresh_module, "create_olap_engine", lambda _settings=None: olap_engine)
    monkeypatch.setattr(refresh_module, "_run_migrations", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(refresh_module, "generate_schema_docs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(refresh_module, "_ensure_lock", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(refresh_module, "_release_lock", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(refresh_module, "read_export_meta", lambda _settings=None: meta)
    monkeypatch.setattr(refresh_module, "iter_export_rows", lambda _settings=None: iter(envelopes))

    yield {
        "settings": settings,
        "meta": meta,
        "envelopes": envelopes,
        "oltp_engine": oltp_engine,
        "olap_engine": olap_engine,
    }

    oltp_engine.dispose()
    olap_engine.dispose()


class TestRefreshPipeline:
    def test_run_refresh_backfills_missing_route_slug_from_first_message(self, refresh_runtime) -> None:
        settings = refresh_runtime["settings"]
        refresh_runtime["envelopes"][:] = [
            _conversation_envelope(
                session_id="session-a",
                first_message="Normalize this title on first persistence",
                ended_at_ms=1_763_200_010_000,
                source_file_modified_at_ms=1_763_200_020_000,
            )
        ]

        with Session(refresh_runtime["oltp_engine"]) as session:
            session.add(
                ConversationRecord(
                    conversation_id="claude:session-a",
                    provider="claude",
                    session_id="session-a",
                    project_path="-Users-tony-Code-helaicopter",
                    project_name="helaicopter",
                    thread_type="main",
                    first_message="stale",
                    route_slug="",
                    started_at=datetime(2026, 3, 10, 9, 0, tzinfo=UTC),
                    ended_at=datetime(2026, 3, 10, 9, 5, tzinfo=UTC),
                    message_count=1,
                    model="claude-sonnet-4-5",
                    total_input_tokens=0,
                    total_output_tokens=0,
                    total_cache_write_tokens=0,
                    total_cache_read_tokens=0,
                    total_reasoning_tokens=0,
                    tool_use_count=0,
                    subagent_count=0,
                    task_count=0,
                    loaded_at=datetime(2026, 3, 10, 9, 5, tzinfo=UTC),
                    first_ingested_at=datetime(2026, 3, 10, 9, 5, tzinfo=UTC),
                    last_refreshed_at=datetime(2026, 3, 10, 9, 5, tzinfo=UTC),
                )
            )
            session.commit()

        refresh_module.run_refresh(
            force=False,
            trigger="manual",
            stale_after_seconds=0,
            settings=settings,
        )

        with Session(refresh_runtime["oltp_engine"]) as session:
            row = session.get(ConversationRecord, "claude:session-a")

        assert row is not None
        assert row.first_message == "Normalize this title on first persistence"
        assert row.route_slug == _derive_route_slug("Normalize this title on first persistence")

    def test_run_refresh_reconciles_only_changed_and_deleted_conversations(self, refresh_runtime) -> None:
        settings = refresh_runtime["settings"]
        refresh_runtime["envelopes"][:] = [
            _export_envelope("session-a", timestamp_ms=1_710_000_000_000, total_input_tokens=100),
            _export_envelope("session-b", timestamp_ms=1_710_000_600_000, total_input_tokens=200),
        ]

        initial_payload = refresh_module.run_refresh(
            force=False,
            trigger="manual",
            stale_after_seconds=0,
            settings=settings,
        )

        refresh_runtime["meta"].conversation_count = 2
        refresh_runtime["meta"].input_key = "input-key-456"
        refresh_runtime["envelopes"][:] = [
            _export_envelope("session-a", timestamp_ms=1_710_000_000_000, total_input_tokens=100),
            _export_envelope("session-b", timestamp_ms=1_710_000_600_000, total_input_tokens=250),
        ]

        incremental_payload = refresh_module.run_refresh(
            force=False,
            trigger="poller",
            stale_after_seconds=0,
            settings=settings,
        )

        with Session(refresh_runtime["oltp_engine"]) as session:
            rows = session.scalars(
                select(ConversationRecord).order_by(ConversationRecord.session_id.asc())
            ).all()
            refresh_runs = session.execute(select(refresh_module.RefreshRun.trigger)).scalars().all()

        with Session(refresh_runtime["olap_engine"]) as session:
            fact_rows = session.scalars(
                select(FactConversation).order_by(FactConversation.session_id.asc())
            ).all()

        assert initial_payload["status"] == "completed"
        assert incremental_payload["status"] == "completed"
        assert [row.session_id for row in rows] == ["session-a", "session-b"]
        assert [row.total_input_tokens for row in rows] == [100, 250]
        assert [row.session_id for row in fact_rows] == ["session-a", "session-b"]
        assert [row.total_input_tokens for row in fact_rows] == [100, 250]
        assert refresh_runs == ["manual", "poller"]
        assert json.loads(
            (settings.database.runtime_dir / "refresh_state.json").read_text(encoding="utf-8")
        ) == {
            "claude:session-a": refresh_module._conversation_refresh_hash(refresh_runtime["envelopes"][0]),
            "claude:session-b": refresh_module._conversation_refresh_hash(refresh_runtime["envelopes"][1]),
        }

    def test_run_refresh_force_rebuild_reloads_all_rows(self, refresh_runtime, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = refresh_runtime["settings"]
        refresh_runtime["envelopes"][:] = [
            _export_envelope("session-a", timestamp_ms=1_710_000_000_000, total_input_tokens=100),
            _export_envelope("session-b", timestamp_ms=1_710_000_600_000, total_input_tokens=200),
        ]
        refresh_module.run_refresh(
            force=False,
            trigger="manual",
            stale_after_seconds=0,
            settings=settings,
        )

        refresh_runtime["meta"].conversation_count = 1
        refresh_runtime["meta"].input_key = "input-key-789"
        refresh_runtime["envelopes"][:] = [
            _export_envelope("session-c", timestamp_ms=1_710_001_200_000, total_input_tokens=300),
        ]

        calls: list[tuple[str, tuple[object, ...]]] = []
        original_reset = refresh_module._reset_oltp_data
        original_load = refresh_module._load_conversation

        def tracking_reset(session: Session) -> None:
            calls.append(("reset", ()))
            original_reset(session)

        def tracking_load(*args: object, **kwargs: object) -> None:
            envelope = args[2]
            calls.append(("load", (envelope["summary"]["sessionId"],)))
            original_load(*args, **kwargs)

        monkeypatch.setattr(refresh_module, "_reset_oltp_data", tracking_reset)
        monkeypatch.setattr(refresh_module, "_load_conversation", tracking_load)

        refresh_module.run_refresh(
            force=True,
            trigger="manual-force",
            stale_after_seconds=0,
            settings=settings,
        )

        with Session(refresh_runtime["oltp_engine"]) as session:
            rows = session.scalars(select(ConversationRecord).order_by(ConversationRecord.session_id.asc())).all()

        assert calls == [("reset", ()), ("load", ("session-c",))]
        assert [row.session_id for row in rows] == ["session-c"]
