"""Port protocols for OpenClaw filesystem session discovery."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel


class OpenClawDiscoverySnapshot(BaseModel):
    """Cheap filesystem snapshot used to detect OpenClaw discovery changes."""

    sessions_dir_mtimes: dict[str, float]
    session_store_mtimes: dict[str, float]
    signature: str


class OpenClawTranscriptArtifact(BaseModel):
    """A transcript-family artifact discovered under ``~/.openclaw/agents``."""

    agent_id: str
    session_id: str
    path: str
    modified_at: float
    content: str
    kind: Literal["live_transcript", "reset_archive", "deleted_archive"]


class OpenClawSessionStoreArtifact(BaseModel):
    """Structured metadata from one agent's ``sessions.json`` store."""

    agent_id: str
    path: str
    modified_at: float
    entries: dict[str, dict[str, object]]


class OpenClawMemoryStoreArtifact(BaseModel):
    """Filesystem metadata for the OpenClaw memory SQLite store."""

    path: str
    modified_at: float
    exists: bool


OpenClawSessionArtifact = OpenClawTranscriptArtifact


@runtime_checkable
class OpenClawStore(Protocol):
    """Read OpenClaw session families from the local filesystem."""

    def read_discovery_snapshot(self) -> OpenClawDiscoverySnapshot:
        """Return mtime-only discovery state for polling and cache invalidation."""
        ...

    def list_transcript_artifacts(self) -> list[OpenClawTranscriptArtifact]:
        """Return all discovered transcript-family artifacts, newest first."""
        ...

    def read_session_store(self, *, agent_id: str) -> OpenClawSessionStoreArtifact | None:
        """Return one agent's ``sessions.json`` metadata, if present."""
        ...

    def read_memory_store_metadata(self) -> OpenClawMemoryStoreArtifact:
        """Return metadata for ``memory/main.sqlite`` without opening the database."""
        ...

    def list_session_artifacts(self) -> list[OpenClawSessionArtifact]:
        """Return live transcript artifacts for compatibility with existing callers."""
        ...

    def read_session_artifact(
        self,
        *,
        agent_id: str,
        session_id: str,
    ) -> OpenClawSessionArtifact | None:
        """Read one live OpenClaw session artifact by agent and session identifier."""
        ...
