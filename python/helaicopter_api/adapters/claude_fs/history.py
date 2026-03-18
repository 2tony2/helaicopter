"""Concrete history reader – loads ``~/.claude/history.jsonl``."""

from __future__ import annotations

import json
import logging

from helaicopter_api.ports.claude_fs import HistoryEntry
from helaicopter_api.adapters.claude_fs.raw import ClaudeArtifactStore, RawArtifact

logger = logging.getLogger(__name__)


class FileHistoryReader:
    """Reads command history entries from a JSONL file."""

    def __init__(self, artifact_store: ClaudeArtifactStore) -> None:
        self._artifact_store = artifact_store

    # -- Port implementation -------------------------------------------------

    def read_history(self, *, limit: int | None = None) -> list[HistoryEntry]:
        artifact = self._artifact_store.read_history_file()
        if artifact is None:
            return []

        entries = _parse_history(artifact)
        # Sort newest-first
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        if limit is not None:
            entries = entries[:limit]
        return entries


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_KEY_MAP = {
    "pastedContents": "pasted_contents",
}


def _parse_history(artifact: RawArtifact) -> list[HistoryEntry]:
    """Parse history JSONL, skipping malformed lines."""
    entries: list[HistoryEntry] = []
    for lineno, line in enumerate(artifact.content.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("Skipping malformed history line at %s:%d", artifact.path, lineno)
            continue
        if not isinstance(raw, dict):
            continue
        # Normalise keys
        normalised = {_KEY_MAP.get(k, k): v for k, v in raw.items()}
        if "display" not in normalised:
            continue
        try:
            entries.append(HistoryEntry.model_validate(normalised))
        except Exception:  # noqa: BLE001
            logger.debug(
                "Skipping unparseable history entry at %s:%d", artifact.path, lineno
            )
    return entries
