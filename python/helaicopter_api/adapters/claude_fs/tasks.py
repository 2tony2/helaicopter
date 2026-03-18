"""Concrete Claude task reader."""

from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from helaicopter_api.adapters.claude_fs.raw import ClaudeArtifactStore
from helaicopter_api.ports.claude_fs import ClaudeTaskPayload

logger = logging.getLogger(__name__)


class FileTaskReader:
    """Read JSON task payloads from ``~/.claude/tasks/<session_id>/``."""

    def __init__(self, artifact_store: ClaudeArtifactStore) -> None:
        self._artifact_store = artifact_store

    def read_tasks(self, session_id: str) -> list[ClaudeTaskPayload]:
        tasks: list[ClaudeTaskPayload] = []
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
                try:
                    tasks.append(ClaudeTaskPayload.model_validate(parsed))
                except ValidationError:
                    logger.debug("Skipping unparseable task JSON at %s", artifact.path)
        return tasks
