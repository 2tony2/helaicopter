"""Port protocols for Codex session artifacts and SQLite metadata."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class CodexSessionArtifact(BaseModel):
    """A raw Codex session JSONL file discovered under ``~/.codex/sessions``."""

    session_id: str
    path: str
    modified_at: float
    content: str


class CodexThreadRecord(BaseModel):
    """Thread metadata row read from ``state_5.sqlite``."""

    id: str
    title: str | None = None
    cwd: str | None = None
    source: str | None = None
    model_provider: str | None = None
    tokens_used: int | None = None
    git_sha: str | None = None
    git_branch: str | None = None
    git_origin_url: str | None = None
    cli_version: str | None = None
    first_user_message: str | None = None
    created_at: int | None = None
    updated_at: int | None = None
    rollout_path: str | None = None
    agent_role: str | None = None
    agent_nickname: str | None = None


class CodexHistoryEntry(BaseModel):
    """One entry from ``~/.codex/history.jsonl``."""

    display: str
    timestamp: float = 0
    project: str | None = None


@runtime_checkable
class CodexStore(Protocol):
    """Read raw Codex session artifacts and thread metadata."""

    def list_session_artifacts(self) -> list[CodexSessionArtifact]:
        """Return all discovered session files, newest first."""
        ...

    def read_session_artifact(self, session_id: str) -> CodexSessionArtifact | None:
        """Read a single session file by its UUID-derived session id."""
        ...

    def list_threads(self) -> list[CodexThreadRecord]:
        """Return all thread metadata rows from the Codex SQLite state DB."""
        ...

    def get_thread(self, thread_id: str) -> CodexThreadRecord | None:
        """Return metadata for one thread id, or ``None`` if unavailable."""
        ...

    def read_history(self, *, limit: int | None = None) -> list[CodexHistoryEntry]:
        """Return Codex CLI history entries, newest first."""
        ...
