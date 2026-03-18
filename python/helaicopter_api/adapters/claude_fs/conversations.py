"""Concrete conversation reader – loads JSONL session files from disk."""

from __future__ import annotations

import json
import logging

from helaicopter_api.ports.claude_fs import (
    ProjectDir,
    RawConversationEvent,
    SessionInfo,
)
from helaicopter_api.adapters.claude_fs.raw import ClaudeArtifactStore, RawArtifact

logger = logging.getLogger(__name__)


class FileConversationReader:
    """Reads Claude conversation JSONL files from ``~/.claude/projects/``."""

    def __init__(self, artifact_store: ClaudeArtifactStore) -> None:
        self._artifact_store = artifact_store

    # -- Port implementation -------------------------------------------------

    def list_projects(self) -> list[ProjectDir]:
        results: list[ProjectDir] = []
        for entry in self._artifact_store.list_project_dirs():
            session_ids = [path.stem for path in self._artifact_store.list_session_files(entry.name)]
            if session_ids:
                results.append(
                    ProjectDir(
                        dir_name=entry.name,
                        full_path=str(entry),
                        session_ids=sorted(session_ids),
                    )
                )
        return results

    def list_sessions(self, project_dir: str) -> list[SessionInfo]:
        infos: list[SessionInfo] = []
        for p in self._artifact_store.list_session_files(project_dir):
            stat = p.stat()
            infos.append(
                SessionInfo(
                    session_id=p.stem,
                    project_dir=project_dir,
                    path=str(p),
                    size_bytes=stat.st_size,
                    modified_at=stat.st_mtime,
                )
            )
        return infos

    def read_session_events(
        self, project_dir: str, session_id: str
    ) -> list[RawConversationEvent]:
        artifact = self._artifact_store.read_session_file(project_dir, session_id)
        if artifact is None:
            return []
        return _parse_jsonl_events(artifact)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_jsonl_events(artifact: RawArtifact) -> list[RawConversationEvent]:
    """Parse a JSONL file into a list of events, skipping malformed lines."""
    events: list[RawConversationEvent] = []
    for lineno, line in enumerate(artifact.content.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("Skipping malformed JSON at %s:%d", artifact.path, lineno)
            continue
        if not isinstance(raw, dict):
            continue
        # Normalise camelCase keys used by the Claude CLI to snake_case
        normalised = _normalise_keys(raw)
        try:
            events.append(RawConversationEvent.model_validate(normalised))
        except Exception:  # noqa: BLE001
            logger.debug("Skipping unparseable event at %s:%d", artifact.path, lineno)
    return events


def _normalise_keys(raw: dict) -> dict:
    """Map the most common camelCase keys from the CLI to snake_case."""
    mapping = {
        "parentUuid": "parent_uuid",
        "sessionId": "session_id",
        "gitBranch": "git_branch",
        "planContent": "plan_content",
    }
    out: dict = {}
    for k, v in raw.items():
        out[mapping.get(k, k)] = v
    return out
