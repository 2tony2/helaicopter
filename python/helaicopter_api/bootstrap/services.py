"""Concrete service assembly.

All heavyweight construction happens here so that route modules never
perform hidden initialisation.  The ``BackendServices`` dataclass is
attached to ``app.state.services`` during startup.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from ..adapters.app_sqlite import SqliteAppStore
from ..adapters.claude_fs import (
    ClaudeArtifactStore,
    FileConversationReader,
    FileHistoryReader,
    FilePlanReader,
    FileTaskReader,
)
from ..adapters.codex_sqlite import FileCodexStore
from ..adapters.evaluation_jobs import LocalCliEvaluationRunner, SupportsSubprocessRun
from ..adapters.oats_artifacts import FileOatsRunStore
from ..adapters.openclaw_fs.store import FileOpenClawStore
from ..adapters.prefect_http import PrefectHttpAdapter
from ..ports.app_sqlite import AppSqliteStore
from ..ports.claude_fs import ConversationReader, HistoryReader, PlanReader, TaskReader
from ..ports.codex_sqlite import CodexStore
from ..ports.evaluations import EvaluationJobRunner
from ..ports.orchestration import OatsRunStore
from ..ports.openclaw_fs import OpenClawStore
from ..ports.prefect import PrefectOrchestrationPort
from ..server.config import Settings


# ---------------------------------------------------------------------------
# Lightweight local cache
# ---------------------------------------------------------------------------


class LocalCache:
    """Trivial in-process key/value store (dict wrapper)."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float | None]] = {}

    def _is_expired(self, expires_at: float | None) -> bool:
        return expires_at is not None and expires_at <= time.monotonic()

    def get(self, key: str, default: Any = None) -> Any:
        entry = self._store.get(key)
        if entry is None:
            return default
        value, expires_at = entry
        if self._is_expired(expires_at):
            self.delete(key)
            return default
        return value

    def set(self, key: str, value: Any, *, ttl_seconds: float | None = None) -> None:
        expires_at = None if ttl_seconds is None else time.monotonic() + ttl_seconds
        self._store[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def delete_many(self, keys: list[str]) -> None:
        for key in keys:
            self.delete(key)

    def keys(self) -> list[str]:
        return list(self._store.keys())


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------


class SubprocessRunner:
    """Thin wrapper around :func:`subprocess.run` for testability."""

    def run(
        self,
        cmd: list[str],
        *,
        cwd: Path | None = None,
        timeout: float | None = 60,
        capture_output: bool = True,
        input_text: str | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            cwd=cwd,
            timeout=timeout,
            capture_output=capture_output,
            input=input_text,
            env=env,
            text=True,
            check=False,
        )


# ---------------------------------------------------------------------------
# Composite service bag
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class BackendServices:
    """All concrete backend services, assembled once at startup."""

    settings: Settings
    sqlite_engine: Engine
    app_sqlite_store: AppSqliteStore
    claude_conversation_reader: ConversationReader
    claude_plan_reader: PlanReader
    claude_history_reader: HistoryReader
    claude_task_reader: TaskReader
    codex_store: CodexStore
    openclaw_store: OpenClawStore
    oats_run_store: OatsRunStore
    prefect_client: PrefectOrchestrationPort
    cache: LocalCache = field(default_factory=LocalCache)
    subprocess_runner: SubprocessRunner = field(default_factory=SubprocessRunner)
    evaluation_job_runner: EvaluationJobRunner | None = None


def invalidate_backend_read_caches(services: BackendServices) -> None:
    """Drop in-process read caches after database artifacts change.

    The SQLite engine is also disposed so subsequent requests reopen fresh
    connections instead of reusing pooled handles created before a refresh.
    """
    exact_keys = [
        "analytics",
        "codex_session_artifacts",
        "codex_threads_by_id",
        "database_status",
        "projects",
    ]
    prefixes = (
        "conversation_summaries:",
        "conversation_detail:",
        "conversation_ref:",
        "conversation_dags:",
        "conversation_dag:",
    )
    cache_keys = []
    if hasattr(services.cache, "keys"):
        cache_keys = [key for key in services.cache.keys() if isinstance(key, str)]
    elif hasattr(services.cache, "values"):
        values = getattr(services.cache, "values")
        if isinstance(values, dict):
            cache_keys = [key for key in values if isinstance(key, str)]

    keys_to_delete = exact_keys + [
        key for key in cache_keys if any(key.startswith(prefix) for prefix in prefixes)
    ]
    if hasattr(services.cache, "delete_many"):
        services.cache.delete_many(keys_to_delete)
    else:
        for key in keys_to_delete:
            services.cache.delete(key)
    services.sqlite_engine.dispose()


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def _build_sqlite_engine(settings: Settings) -> Engine:
    db_path = settings.app_sqlite_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{db_path}",
        echo=settings.debug,
        connect_args={"check_same_thread": False},
    )


def build_services(settings: Settings) -> BackendServices:
    """Construct the full service bag from *settings*.

    This is the single entry-point for wiring – nothing else should
    call ``create_engine`` or instantiate caches directly.
    """
    engine = _build_sqlite_engine(settings)
    claude_artifacts = ClaudeArtifactStore(
        projects_dir=settings.claude_projects_dir,
        plans_dir=settings.claude_plans_dir,
        history_file=settings.claude_history_file,
        tasks_dir=settings.claude_tasks_dir,
    )
    app_sqlite_store = SqliteAppStore(db_path=settings.app_sqlite_path)
    codex_store = FileCodexStore(
        sessions_dir=settings.codex_sessions_dir,
        db_path=settings.codex_sqlite_path,
        history_file=settings.codex_history_file,
    )
    openclaw_store = FileOpenClawStore(agents_dir=settings.openclaw_agents_dir)
    prefect_client = PrefectHttpAdapter.from_settings(settings.prefect)
    oats_run_store = FileOatsRunStore(
        project_root=settings.project_root,
        runtime_dir=settings.runtime_dir,
    )
    subprocess_runner = SubprocessRunner()
    evaluation_subprocess_runner = cast(SupportsSubprocessRun, subprocess_runner)
    return BackendServices(
        settings=settings,
        sqlite_engine=engine,
        app_sqlite_store=app_sqlite_store,
        claude_conversation_reader=FileConversationReader(claude_artifacts),
        claude_plan_reader=FilePlanReader(claude_artifacts),
        claude_history_reader=FileHistoryReader(claude_artifacts),
        claude_task_reader=FileTaskReader(claude_artifacts),
        codex_store=codex_store,
        openclaw_store=openclaw_store,
        oats_run_store=oats_run_store,
        prefect_client=prefect_client,
        subprocess_runner=subprocess_runner,
        evaluation_job_runner=LocalCliEvaluationRunner(
            subprocess_runner=evaluation_subprocess_runner
        ),
    )
