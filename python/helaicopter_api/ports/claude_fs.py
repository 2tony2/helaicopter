"""Port protocols for Claude filesystem artifact access.

Application-layer code depends on these protocols, never on the concrete
adapters directly.  Bootstrap wires the real implementations at startup.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Value objects returned by the ports
# ---------------------------------------------------------------------------


class RawConversationEvent(BaseModel):
    """Single JSONL event from a Claude session file."""

    type: str
    uuid: str = ""
    parent_uuid: str | None = None
    timestamp: float | str = 0
    session_id: str | None = None
    git_branch: str | None = None
    message: dict | None = None
    plan_content: str | None = None
    slug: str | None = None
    cwd: str | None = None
    data: dict | None = None

    model_config = {"extra": "allow"}


class SessionInfo(BaseModel):
    """Lightweight metadata about a session file on disk."""

    session_id: str
    project_dir: str
    path: str
    size_bytes: int
    modified_at: float


class HistoryEntry(BaseModel):
    """Single entry from ``~/.claude/history.jsonl``."""

    display: str
    timestamp: float = 0
    project: str | None = None
    pasted_contents: dict | None = None


class PlanFile(BaseModel):
    """Raw plan file content from ``~/.claude/plans/``."""

    slug: str
    path: str
    content: str
    modified_at: float


class ProjectDir(BaseModel):
    """A project directory under ``~/.claude/projects/``."""

    dir_name: str
    full_path: str
    session_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Port protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class ConversationReader(Protocol):
    """Read raw conversation JSONL events from the Claude filesystem."""

    def list_projects(self) -> list[ProjectDir]:
        """Return all project directories that contain session files."""
        ...

    def list_sessions(self, project_dir: str) -> list[SessionInfo]:
        """Return session metadata for a given project directory name."""
        ...

    def read_session_events(self, project_dir: str, session_id: str) -> list[RawConversationEvent]:
        """Read and parse all JSONL events for a session."""
        ...


@runtime_checkable
class PlanReader(Protocol):
    """Read raw plan markdown files from ``~/.claude/plans/``."""

    def list_plans(self) -> list[PlanFile]:
        """Return all plan files with their content."""
        ...

    def read_plan(self, slug: str) -> PlanFile | None:
        """Read a single plan by slug.  Returns *None* if not found."""
        ...


@runtime_checkable
class HistoryReader(Protocol):
    """Read command history from ``~/.claude/history.jsonl``."""

    def read_history(self, *, limit: int | None = None) -> list[HistoryEntry]:
        """Return history entries, newest first.

        If *limit* is given, return at most that many entries.
        """
        ...


@runtime_checkable
class TaskReader(Protocol):
    """Read task payloads from ``~/.claude/tasks/<session_id>/``."""

    def read_tasks(self, session_id: str) -> list[dict[str, Any]]:
        """Return all JSON task payloads for one session, newest file-order independent."""
        ...
