"""Concrete Claude task reader."""

from __future__ import annotations

import json
import logging
from typing import Any

from helaicopter_api.adapters.claude_fs.raw import ClaudeArtifactStore

logger = logging.getLogger(__name__)


class FileTaskReader:
    """Read JSON task payloads from ``~/.claude/tasks/<session_id>/``."""

    def __init__(self, artifact_store: ClaudeArtifactStore) -> None:
        self._artifact_store = artifact_store

    def read_tasks(self, session_id: str) -> list[dict[str, Any]]:
        tasks: list[dict[str, Any]] = []
        for path in self._artifact_store.list_task_files(session_id):
            artifact = self._artifact_store.read_task_file(session_id, path.name)
            if artifact is None:
                continue
            try:
                parsed = json.loads(artifact.content)
            except json.JSONDecodeError:
                logger.debug("Skipping malformed task JSON at %s", artifact.path)
                continue
            if isinstance(parsed, dict):
                tasks.append(parsed)
        return tasks
