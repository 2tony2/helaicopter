"""Concrete Codex adapter backed by session files and ``state_5.sqlite``."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import quote

from helaicopter_api.ports.codex_sqlite import (
    CodexHistoryEntry,
    CodexSessionArtifact,
    CodexStore,
    CodexThreadRecord,
)

_SESSION_ID_SUFFIX = ".jsonl"
_SESSION_ID_PATTERN = re.compile(
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\.jsonl$"
)


class FileCodexStore(CodexStore):
    """Read raw Codex session artifacts and thread metadata from local disk."""

    def __init__(self, *, sessions_dir: Path, db_path: Path, history_file: Path) -> None:
        self._sessions_dir = sessions_dir
        self._db_path = db_path
        self._history_file = history_file

    def list_session_artifacts(self) -> list[CodexSessionArtifact]:
        artifacts: list[CodexSessionArtifact] = []
        for path in self._iter_session_paths():
            artifact = self._artifact_for_path(path)
            if artifact is not None:
                artifacts.append(artifact)
        return sorted(artifacts, key=lambda artifact: artifact.modified_at, reverse=True)

    def read_session_artifact(self, session_id: str) -> CodexSessionArtifact | None:
        for path in self._iter_session_paths():
            if self._session_id_for_path(path) != session_id:
                continue
            return self._artifact_for_path(path)
        return None

    def list_threads(self) -> list[CodexThreadRecord]:
        connection = self._connect_readonly()
        if connection is None:
            return []

        try:
            if not _table_exists(connection, "threads"):
                return []
            rows = connection.execute(
                """
                SELECT
                  id,
                  title,
                  cwd,
                  source,
                  model_provider,
                  tokens_used,
                  git_sha,
                  git_branch,
                  git_origin_url,
                  cli_version,
                  first_user_message,
                  created_at,
                  updated_at,
                  rollout_path,
                  agent_role,
                  agent_nickname
                FROM threads
                ORDER BY COALESCE(updated_at, created_at, 0) DESC, id ASC
                """
            ).fetchall()
            return [_map_thread_row(row) for row in rows]
        finally:
            connection.close()

    def get_thread(self, thread_id: str) -> CodexThreadRecord | None:
        connection = self._connect_readonly()
        if connection is None:
            return None

        try:
            if not _table_exists(connection, "threads"):
                return None
            row = connection.execute(
                """
                SELECT
                  id,
                  title,
                  cwd,
                  source,
                  model_provider,
                  tokens_used,
                  git_sha,
                  git_branch,
                  git_origin_url,
                  cli_version,
                  first_user_message,
                  created_at,
                  updated_at,
                  rollout_path,
                  agent_role,
                  agent_nickname
                FROM threads
                WHERE id = ?
                """,
                (thread_id,),
            ).fetchone()
            return _map_thread_row(row) if row is not None else None
        finally:
            connection.close()

    def read_history(self, *, limit: int | None = None) -> list[CodexHistoryEntry]:
        if not self._history_file.is_file():
            return []

        entries: list[CodexHistoryEntry] = []
        try:
            for line in self._history_file.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(parsed, dict):
                    continue
                entries.append(
                    CodexHistoryEntry(
                        display=str(parsed.get("text") or ""),
                        timestamp=float(parsed.get("ts") or 0) * 1000,
                        project=parsed.get("session_id") if isinstance(parsed.get("session_id"), str) else None,
                    )
                )
        except OSError:
            return []

        entries.sort(key=lambda entry: entry.timestamp, reverse=True)
        if limit is not None:
            return entries[:limit]
        return entries

    def _iter_session_paths(self) -> list[Path]:
        if not self._sessions_dir.exists():
            return []
        return sorted(
            (
                path
                for path in self._sessions_dir.rglob(f"*{_SESSION_ID_SUFFIX}")
                if path.is_file() and self._session_id_for_path(path) is not None
            ),
            reverse=True,
        )

    def _artifact_for_path(self, path: Path) -> CodexSessionArtifact | None:
        session_id = self._session_id_for_path(path)
        if session_id is None:
            return None
        try:
            stat = path.stat()
            content = path.read_text(encoding="utf-8")
        except OSError:
            return None
        return CodexSessionArtifact(
            session_id=session_id,
            path=str(path),
            modified_at=stat.st_mtime,
            content=content,
        )

    def _session_id_for_path(self, path: Path) -> str | None:
        match = _SESSION_ID_PATTERN.search(path.name)
        if match is None:
            return None
        candidate = match.group(1)
        return candidate if _looks_like_uuid(candidate) else None

    def _connect_readonly(self) -> sqlite3.Connection | None:
        if not self._db_path.exists():
            return None
        uri = f"file:{quote(str(self._db_path))}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        return connection


def _looks_like_uuid(value: str) -> bool:
    parts = value.split("-")
    expected = [8, 4, 4, 4, 12]
    return len(parts) == len(expected) and all(
        len(part) == size and all(char in "0123456789abcdefABCDEF" for char in part)
        for part, size in zip(parts, expected, strict=True)
    )


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _map_thread_row(row: sqlite3.Row) -> CodexThreadRecord:
    return CodexThreadRecord(
        id=row["id"],
        title=row["title"],
        cwd=row["cwd"],
        source=row["source"],
        model_provider=row["model_provider"],
        tokens_used=row["tokens_used"],
        git_sha=row["git_sha"],
        git_branch=row["git_branch"],
        git_origin_url=row["git_origin_url"],
        cli_version=row["cli_version"],
        first_user_message=row["first_user_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        rollout_path=row["rollout_path"],
        agent_role=row["agent_role"],
        agent_nickname=row["agent_nickname"],
    )
