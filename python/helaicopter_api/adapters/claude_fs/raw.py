"""Low-level Claude filesystem access.

This module is intentionally limited to locating and reading artifacts from
``~/.claude``. Higher-level parsing stays in the focused reader modules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RawArtifact:
    """Raw text artifact loaded from disk."""

    path: Path
    content: str
    modified_at: float
    size_bytes: int


class ClaudeArtifactStore:
    """Direct filesystem access for Claude conversation, plan, and history files."""

    def __init__(
        self,
        *,
        projects_dir: Path,
        plans_dir: Path,
        history_file: Path,
        tasks_dir: Path,
    ) -> None:
        self._projects_dir = projects_dir
        self._plans_dir = plans_dir
        self._history_file = history_file
        self._tasks_dir = tasks_dir

    def list_project_dirs(self) -> list[Path]:
        return self._sorted_dir_entries(self._projects_dir)

    def list_session_files(self, project_dir: str) -> list[Path]:
        return self._sorted_files(self._projects_dir / project_dir, suffix=".jsonl")

    def read_session_file(self, project_dir: str, session_id: str) -> RawArtifact | None:
        return self._read_artifact(self._projects_dir / project_dir / f"{session_id}.jsonl")

    def list_plan_files(self) -> list[Path]:
        return self._sorted_files(self._plans_dir, suffix=".md")

    def read_plan_file(self, slug: str) -> RawArtifact | None:
        return self._read_artifact(self._plans_dir / f"{slug}.md")

    def read_history_file(self) -> RawArtifact | None:
        return self._read_artifact(self._history_file)

    def list_task_files(self, session_id: str) -> list[Path]:
        return self._sorted_files(self._tasks_dir / session_id, suffix=".json")

    def read_task_file(self, session_id: str, filename: str) -> RawArtifact | None:
        return self._read_artifact(self._tasks_dir / session_id / filename)

    def _sorted_dir_entries(self, root: Path) -> list[Path]:
        if not root.is_dir():
            return []
        return sorted(entry for entry in root.iterdir() if entry.is_dir())

    def _sorted_files(self, root: Path, *, suffix: str) -> list[Path]:
        if not root.is_dir():
            return []
        return sorted(
            entry
            for entry in root.iterdir()
            if entry.is_file() and entry.suffix == suffix
        )

    def _read_artifact(self, path: Path) -> RawArtifact | None:
        if not path.is_file():
            return None
        try:
            stat = path.stat()
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.warning("Could not read Claude artifact: %s", path)
            return None
        return RawArtifact(
            path=path,
            content=content,
            modified_at=stat.st_mtime,
            size_bytes=stat.st_size,
        )
