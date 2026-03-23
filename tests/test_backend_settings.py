from __future__ import annotations

import json
import sqlite3

import pytest
from pydantic import ValidationError

from helaicopter_api.application.analytics import get_analytics
from helaicopter_api.bootstrap.services import build_services
from helaicopter_api.server.dev_instance import build_checkout_instance
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
                "health": "healthy",
                "operationalStatus": "Readable and serving historical conversations",
                "note": "App-local metadata",
                "error": None,
                "path": path,
                "target": None,
                "tableCount": 0,
                "tables": [],
                "sizeBytes": 0,
                "sizeDisplay": "0 B",
                "inventorySummary": "No tables recorded",
                "load": [],
            },
        },
    }


def test_settings_expose_nested_cli_and_database_sections(tmp_path) -> None:
    settings = Settings(
        project_root=tmp_path,
        claude_dir=tmp_path / ".claude",
        codex_dir=tmp_path / ".codex",
        openclaw_dir=tmp_path / ".openclaw",
        opencloud_dir=tmp_path / ".local" / "share" / "opencode",
    )

    assert settings.cli.claude_dir == tmp_path / ".claude"
    assert settings.cli.codex_dir == tmp_path / ".codex"
    assert settings.cli.openclaw_dir == tmp_path / ".openclaw"
    assert settings.cli.opencloud_dir == tmp_path / ".local" / "share" / "opencode"
    assert settings.openclaw_agents_dir == tmp_path / ".openclaw" / "agents"
    assert settings.openclaw_agent_sessions_glob.endswith(".openclaw/agents/*/sessions")
    assert settings.opencloud_sqlite_path == tmp_path / ".local" / "share" / "opencode" / "opencode.db"
    assert settings.database.runtime_dir == tmp_path / ".helaicopter" / "database-runtime"
    assert settings.database.sqlite.path == (
        tmp_path / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"
    )


def test_db_settings_reuse_backend_settings_contract(tmp_path) -> None:
    backend_settings = Settings(project_root=tmp_path)

    database_settings = db_settings.get_database_settings(backend_settings)

    assert database_settings.sqlite.path == backend_settings.database.sqlite.path
    assert database_settings.duckdb.docs_dir == (
        tmp_path / "public" / "database-schemas" / "olap"
    )


def test_db_settings_preserve_legacy_duckdb_alias_for_transition(tmp_path) -> None:
    backend_settings = Settings(project_root=tmp_path)

    assert backend_settings.database.legacy_duckdb is backend_settings.database.duckdb


def test_settings_parse_hela_prefixed_environment_values(monkeypatch, tmp_path) -> None:
    runtime_dir = tmp_path / ".oats" / "custom-runtime"
    monkeypatch.setenv("HELA_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("HELA_OATS_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("HELA_API_PORT", "31506")
    monkeypatch.setenv("HELA_WEB_PORT", "32506")
    monkeypatch.setenv("HELA_DEBUG", "true")

    settings = Settings()

    assert settings.project_root == tmp_path
    assert settings.runtime_dir == runtime_dir
    assert settings.api_port == 31506
    assert settings.web_port == 32506
    assert settings.debug is True


def test_checkout_instance_derives_stable_ports_from_project_root(tmp_path) -> None:
    a = build_checkout_instance(tmp_path / "helaicopter")
    b = build_checkout_instance(tmp_path / "helaicopter")
    c = build_checkout_instance(tmp_path / "helaicopter-main")

    assert a.checkout_id == b.checkout_id
    assert a.api_port == b.api_port
    assert a.web_port == b.web_port
    assert a.api_port != c.api_port
    assert a.web_port != c.web_port


def test_settings_expose_derived_checkout_ports_and_runtime_root(tmp_path) -> None:
    settings = Settings(project_root=tmp_path)

    assert settings.api_port == build_checkout_instance(tmp_path).api_port
    assert settings.web_port == build_checkout_instance(tmp_path).web_port
    assert settings.database.runtime_dir.parent == tmp_path / ".helaicopter"


def test_settings_default_to_git_common_root_when_running_inside_worktree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    repo_root = tmp_path / "repo"
    worktree_root = repo_root / ".worktrees" / "feature"
    worktree_root.mkdir(parents=True)
    (repo_root / ".git").mkdir()
    monkeypatch.chdir(worktree_root)
    monkeypatch.delenv("HELA_PROJECT_ROOT", raising=False)

    def fake_run(command: list[str], **kwargs: object):
        assert command == ["git", "rev-parse", "--git-common-dir"]

        class Completed:
            returncode = 0
            stdout = str(repo_root / ".git") + "\n"
            stderr = ""

        return Completed()

    monkeypatch.setattr("helaicopter_api.server.config.subprocess.run", fake_run)

    settings = Settings()

    assert settings.project_root == repo_root
    assert settings.app_sqlite_path == (
        repo_root / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"
    )


def test_analytics_reads_shared_repo_artifacts_when_started_from_worktree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    repo_root = tmp_path / "repo"
    worktree_root = repo_root / ".worktrees" / "feature"
    db_path = repo_root / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"
    worktree_root.mkdir(parents=True)
    db_path.parent.mkdir(parents=True)
    (repo_root / ".git").mkdir()
    monkeypatch.chdir(worktree_root)
    monkeypatch.delenv("HELA_PROJECT_ROOT", raising=False)

    def fake_run(command: list[str], **kwargs: object):
        assert command == ["git", "rev-parse", "--git-common-dir"]

        class Completed:
            returncode = 0
            stdout = str(repo_root / ".git") + "\n"
            stderr = ""

        return Completed()

    monkeypatch.setattr("helaicopter_api.server.config.subprocess.run", fake_run)

    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE conversations (
              conversation_id TEXT PRIMARY KEY,
              provider TEXT NOT NULL,
              session_id TEXT NOT NULL,
              project_path TEXT NOT NULL,
              project_name TEXT NOT NULL,
              thread_type TEXT NOT NULL DEFAULT 'main',
              first_message TEXT NOT NULL,
              route_slug TEXT,
              started_at TEXT NOT NULL,
              ended_at TEXT NOT NULL,
              message_count INTEGER NOT NULL DEFAULT 0,
              model TEXT,
              git_branch TEXT,
              reasoning_effort TEXT,
              speed TEXT,
              total_input_tokens INTEGER NOT NULL DEFAULT 0,
              total_output_tokens INTEGER NOT NULL DEFAULT 0,
              total_cache_write_tokens INTEGER NOT NULL DEFAULT 0,
              total_cache_read_tokens INTEGER NOT NULL DEFAULT 0,
              total_reasoning_tokens INTEGER NOT NULL DEFAULT 0,
              tool_use_count INTEGER NOT NULL DEFAULT 0,
              subagent_count INTEGER NOT NULL DEFAULT 0,
              task_count INTEGER NOT NULL DEFAULT 0
            );
            """
        )
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
              route_slug,
              started_at,
              ended_at,
              message_count,
              model,
              total_input_tokens
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "claude-1",
                "claude",
                "session-1",
                "-Users-tony-Code-helaicopter",
                "helaicopter",
                "main",
                "Ship the analytics fix",
                "ship-the-analytics-fix",
                "2026-03-23T08:00:00Z",
                "2026-03-23T09:00:00Z",
                3,
                "claude-sonnet-4-5-20250929",
                1000,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    services = build_services(Settings())

    analytics = get_analytics(services, days=7)

    assert analytics.total_conversations == 1
    assert analytics.total_input_tokens == 1000


def test_settings_reject_invalid_hela_environment_values(monkeypatch) -> None:
    monkeypatch.setenv("HELA_DEBUG", "definitely-not-a-bool")

    with pytest.raises(ValidationError):
        Settings()


def test_load_status_uses_shared_backend_project_root(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HELA_PROJECT_ROOT", str(tmp_path))
    status_file = tmp_path / ".helaicopter" / "database-runtime" / "status.json"
    status_file.parent.mkdir(parents=True, exist_ok=True)
    payload = _status_payload(str(tmp_path / "public" / "database-artifacts" / "oltp" / "db.sqlite"))
    status_file.write_text(json.dumps(payload), encoding="utf-8")

    loaded = status_module.load_status()

    assert loaded is not None
    assert loaded["databases"]["frontendCache"]["key"] == "frontend_cache"
    assert "prefectPostgres" not in loaded["databases"]
    assert loaded["databases"]["frontendCache"]["key"] == "frontend_cache"


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
