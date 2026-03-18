from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from helaicopter_api.server.config import Settings
from helaicopter_db import refresh as refresh_module
from helaicopter_db import settings as db_settings
from helaicopter_db import status as status_module


def _status_payload(path: str) -> dict[str, object]:
    return {
        "status": "completed",
        "trigger": "manual",
        "startedAt": "2026-03-17T10:00:00Z",
        "finishedAt": "2026-03-17T10:00:10Z",
        "durationMs": 10_000,
        "error": None,
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
                "path": path,
                "target": None,
                "publicPath": "/database-artifacts/oltp/helaicopter_oltp.sqlite",
                "docsUrl": "/database-schemas/oltp/index.html",
                "tableCount": 0,
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
                "path": f"{path}.duckdb",
                "target": None,
                "publicPath": "/database-artifacts/olap/helaicopter_olap.duckdb",
                "docsUrl": "/database-schemas/olap/index.html",
                "tableCount": 0,
                "tables": [],
            },
        },
    }


def test_settings_expose_nested_cli_and_database_sections(tmp_path) -> None:
    settings = Settings(
        project_root=tmp_path,
        claude_dir=tmp_path / ".claude",
        codex_dir=tmp_path / ".codex",
    )

    assert settings.cli.claude_dir == tmp_path / ".claude"
    assert settings.cli.codex_dir == tmp_path / ".codex"
    assert settings.database.runtime_dir == tmp_path / "var" / "database-runtime"
    assert settings.database.sqlite.path == (
        tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"
    )


def test_db_settings_reuse_backend_settings_contract(tmp_path) -> None:
    backend_settings = Settings(project_root=tmp_path)

    database_settings = db_settings.get_database_settings(backend_settings)

    assert database_settings.sqlite.path == backend_settings.database.sqlite.path
    assert database_settings.legacy_duckdb.docs_dir == (
        tmp_path / "public" / "database-schemas" / "olap"
    )


def test_settings_parse_hela_prefixed_environment_values(monkeypatch, tmp_path) -> None:
    runtime_dir = tmp_path / ".oats" / "custom-runtime"
    monkeypatch.setenv("HELA_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("HELA_OATS_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("HELA_DEBUG", "true")

    settings = Settings()

    assert settings.project_root == tmp_path
    assert settings.runtime_dir == runtime_dir
    assert settings.debug is True


def test_settings_reject_invalid_hela_environment_values(monkeypatch) -> None:
    monkeypatch.setenv("HELA_DEBUG", "definitely-not-a-bool")

    with pytest.raises(ValidationError):
        Settings()


def test_load_status_uses_shared_backend_project_root(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HELA_PROJECT_ROOT", str(tmp_path))
    status_file = tmp_path / "var" / "database-runtime" / "status.json"
    status_file.parent.mkdir(parents=True, exist_ok=True)
    payload = _status_payload(str(tmp_path / "public" / "database-artifacts" / "oltp" / "db.sqlite"))
    status_file.write_text(json.dumps(payload), encoding="utf-8")

    assert status_module.load_status() == payload


def test_run_migrations_uses_shared_backend_project_root(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HELA_PROJECT_ROOT", str(tmp_path))
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(command: list[str], **kwargs: object) -> object:
        calls.append((command, kwargs))
        return object()

    monkeypatch.setattr(refresh_module.subprocess, "run", fake_run)

    refresh_module._run_migrations("oltp")

    assert calls == [
        (
            [
                refresh_module.sys.executable,
                "-m",
                "alembic",
                "-c",
                str(tmp_path / "alembic.ini"),
                "-x",
                "target=oltp",
                "upgrade",
                "head",
            ],
            {
                "check": True,
                "cwd": tmp_path,
                "capture_output": True,
                "text": True,
            },
        )
    ]
