"""Filesystem-backed OpenClaw session discovery."""

from __future__ import annotations

from pathlib import Path

from helaicopter_api.ports.openclaw_fs import OpenClawSessionArtifact


class FileOpenClawStore:
    """Read OpenClaw session JSONL artifacts from ``~/.openclaw/agents/*/sessions``."""

    def __init__(self, *, agents_dir: Path) -> None:
        self._agents_dir = agents_dir

    def list_session_artifacts(self) -> list[OpenClawSessionArtifact]:
        artifacts: list[OpenClawSessionArtifact] = []
        for sessions_dir in sorted(self._agents_dir.glob("*/sessions")):
            agent_id = sessions_dir.parent.name
            for path in sorted(sessions_dir.glob("*.jsonl")):
                stat = path.stat()
                artifacts.append(
                    OpenClawSessionArtifact(
                        agent_id=agent_id,
                        session_id=path.stem,
                        path=str(path),
                        modified_at=stat.st_mtime,
                        content=path.read_text(encoding="utf-8"),
                    )
                )
        artifacts.sort(key=lambda item: (item.modified_at, item.agent_id, item.session_id), reverse=True)
        return artifacts

    def read_session_artifact(
        self,
        *,
        agent_id: str,
        session_id: str,
    ) -> OpenClawSessionArtifact | None:
        path = self._agents_dir / agent_id / "sessions" / f"{session_id}.jsonl"
        if not path.is_file():
            return None
        stat = path.stat()
        return OpenClawSessionArtifact(
            agent_id=agent_id,
            session_id=session_id,
            path=str(path),
            modified_at=stat.st_mtime,
            content=path.read_text(encoding="utf-8"),
        )
