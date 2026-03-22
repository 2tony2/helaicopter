"""Filesystem-backed OpenClaw session discovery."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from helaicopter_api.ports.openclaw_fs import (
    OpenClawDiscoverySnapshot,
    OpenClawMemoryStoreArtifact,
    OpenClawSessionArtifact,
    OpenClawSessionStoreArtifact,
    OpenClawTranscriptArtifact,
)


class FileOpenClawStore:
    """Read OpenClaw session JSONL artifacts from ``~/.openclaw/agents/*/sessions``."""

    def __init__(self, *, agents_dir: Path, memory_sqlite_path: Path) -> None:
        self._agents_dir = agents_dir
        self._memory_sqlite_path = memory_sqlite_path

    def read_discovery_snapshot(self) -> OpenClawDiscoverySnapshot:
        sessions_dir_mtimes: dict[str, float] = {}
        session_store_mtimes: dict[str, float] = {}

        for sessions_dir in self._iter_sessions_dirs():
            try:
                sessions_dir_mtimes[str(sessions_dir)] = sessions_dir.stat().st_mtime
            except (FileNotFoundError, OSError, PermissionError):
                continue

            session_store_path = sessions_dir / "sessions.json"
            try:
                if session_store_path.is_file():
                    session_store_mtimes[str(session_store_path)] = session_store_path.stat().st_mtime
            except (FileNotFoundError, OSError, PermissionError):
                continue

        signature_payload = {
            "session_store_mtimes": sorted(session_store_mtimes.items()),
            "sessions_dir_mtimes": sorted(sessions_dir_mtimes.items()),
        }
        signature = hashlib.sha256(
            json.dumps(signature_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return OpenClawDiscoverySnapshot(
            sessions_dir_mtimes=sessions_dir_mtimes,
            session_store_mtimes=session_store_mtimes,
            signature=signature,
        )

    def list_transcript_artifacts(self) -> list[OpenClawTranscriptArtifact]:
        artifacts: list[OpenClawTranscriptArtifact] = []
        for sessions_dir in self._iter_sessions_dirs():
            agent_id = sessions_dir.parent.name
            for path in self._iter_transcript_paths(sessions_dir):
                artifact = self._read_transcript_artifact(path=path, agent_id=agent_id)
                if artifact is not None:
                    artifacts.append(artifact)
        artifacts.sort(
            key=lambda item: (item.modified_at, item.agent_id, item.session_id, item.path),
            reverse=True,
        )
        return artifacts

    def read_session_store(self, *, agent_id: str) -> OpenClawSessionStoreArtifact | None:
        path = self._agents_dir / agent_id / "sessions" / "sessions.json"
        try:
            if not path.is_file():
                return None
        except (FileNotFoundError, OSError, PermissionError):
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, PermissionError, UnicodeDecodeError, json.JSONDecodeError):
            return None

        entries = payload.get("entries", {})
        if not isinstance(entries, dict):
            entries = {}
        normalized_entries: dict[str, dict[str, object]] = {}
        for key, value in entries.items():
            if isinstance(key, str) and isinstance(value, dict):
                normalized_entries[key] = {
                    entry_key: entry_value
                    for entry_key, entry_value in value.items()
                    if isinstance(entry_key, str)
                }
        try:
            stat = path.stat()
        except (FileNotFoundError, OSError, PermissionError):
            return None
        return OpenClawSessionStoreArtifact(
            agent_id=agent_id,
            path=str(path),
            modified_at=stat.st_mtime,
            entries=normalized_entries,
        )

    def read_memory_store_metadata(self) -> OpenClawMemoryStoreArtifact:
        try:
            exists = self._memory_sqlite_path.is_file()
        except (FileNotFoundError, OSError, PermissionError):
            exists = False
        try:
            modified_at = self._memory_sqlite_path.stat().st_mtime if exists else 0.0
        except (FileNotFoundError, OSError, PermissionError):
            exists = False
            modified_at = 0.0
        return OpenClawMemoryStoreArtifact(
            path=str(self._memory_sqlite_path),
            modified_at=modified_at,
            exists=exists,
        )

    def list_session_artifacts(self) -> list[OpenClawSessionArtifact]:
        return [
            artifact
            for artifact in self.list_transcript_artifacts()
            if artifact.kind == "live_transcript"
        ]

    def read_session_artifact(
        self,
        *,
        agent_id: str,
        session_id: str,
    ) -> OpenClawSessionArtifact | None:
        path = self._agents_dir / agent_id / "sessions" / f"{session_id}.jsonl"
        return self._read_transcript_artifact(path=path, agent_id=agent_id)

    def _iter_sessions_dirs(self) -> list[Path]:
        try:
            candidate_paths = list(self._agents_dir.glob("*/sessions"))
        except (FileNotFoundError, OSError, PermissionError):
            return []

        sessions_dirs: list[Path] = []
        for path in candidate_paths:
            try:
                if path.is_dir():
                    sessions_dirs.append(path)
            except (FileNotFoundError, OSError, PermissionError):
                continue
        return sorted(sessions_dirs)

    def _iter_transcript_paths(self, sessions_dir: Path) -> list[Path]:
        try:
            candidate_paths = list(sessions_dir.iterdir())
        except (FileNotFoundError, OSError, PermissionError):
            return []
        return sorted(
            path for path in candidate_paths if self._classify_transcript_kind(path) is not None
        )

    def _read_transcript_artifact(
        self,
        *,
        path: Path,
        agent_id: str,
    ) -> OpenClawTranscriptArtifact | None:
        kind = self._classify_transcript_kind(path)
        if kind is None:
            return None
        try:
            if not path.is_file():
                return None
            stat = path.stat()
            content = path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError, PermissionError, UnicodeDecodeError):
            return None
        return OpenClawTranscriptArtifact(
            agent_id=agent_id,
            session_id=self._session_id_from_path(path),
            path=str(path),
            modified_at=stat.st_mtime,
            content=content,
            kind=kind,
        )

    def _classify_transcript_kind(
        self,
        path: Path,
    ) -> Literal["live_transcript", "reset_archive", "deleted_archive"] | None:
        name = path.name
        if name.endswith(".jsonl"):
            return "live_transcript"
        if ".jsonl.reset." in name:
            return "reset_archive"
        if ".jsonl.deleted." in name:
            return "deleted_archive"
        return None

    def _session_id_from_path(self, path: Path) -> str:
        name = path.name
        if name.endswith(".jsonl"):
            return path.stem
        for marker in (".jsonl.reset.", ".jsonl.deleted."):
            if marker in name:
                return name.split(marker, 1)[0]
        return path.stem
