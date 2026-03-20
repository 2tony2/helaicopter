"""Concrete Claude task reader."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from helaicopter_api.adapters.claude_fs.raw import ClaudeArtifactStore
from helaicopter_api.ports.claude_fs import ClaudeTaskPayload

logger = logging.getLogger(__name__)


class FileTaskReader:
    """Read JSON task payloads from ``~/.claude/tasks/<session_id>/``."""

    def __init__(self, artifact_store: ClaudeArtifactStore) -> None:
        self._artifact_store = artifact_store

    def read_tasks(
        self,
        session_id: str,
        *,
        parent_session_id: str | None = None,
    ) -> list[ClaudeTaskPayload]:
        tasks: list[ClaudeTaskPayload] = []
        task_files = self._artifact_store.list_task_files(session_id)
        if task_files:
            for path in task_files:
                artifact = self._artifact_store.read_task_file(session_id, path.name)
                if artifact is None:
                    continue
                tasks.extend(self._parse_task_artifact_content(artifact.content, artifact_path=artifact.path))
            return tasks

        if parent_session_id is None:
            return tasks

        for path in self._parent_scoped_task_files(parent_session_id, session_id):
            content = self._read_parent_scoped_task_file(path)
            if content is None:
                continue
            tasks.extend(self._parse_task_artifact_content(content, artifact_path=path))
        return tasks

    def _parent_scoped_task_files(self, parent_session_id: str, session_id: str) -> list[Path]:
        root = self._tasks_dir / parent_session_id / session_id
        if not root.is_dir():
            return []
        return sorted(entry for entry in root.iterdir() if entry.is_file() and entry.suffix == ".json")

    def _read_parent_scoped_task_file(self, path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.warning("Could not read Claude task artifact: %s", path)
            return None

    def _parse_task_artifact_content(
        self,
        content: str,
        *,
        artifact_path: Path,
    ) -> list[ClaudeTaskPayload]:
        tasks: list[ClaudeTaskPayload] = []
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            logger.debug("Skipping malformed task JSON at %s", artifact_path)
            return tasks
        if isinstance(parsed, dict):
            try:
                tasks.append(ClaudeTaskPayload.model_validate(parsed))
            except ValidationError:
                logger.debug("Skipping unparseable task JSON at %s", artifact_path)
        return tasks

    @property
    def _tasks_dir(self) -> Path:
        return self._artifact_store._tasks_dir
