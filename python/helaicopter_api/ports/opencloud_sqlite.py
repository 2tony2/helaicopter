"""Port protocols for OpenCloud/OpenCode SQLite-backed sessions."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class OpenCloudSessionRecord(BaseModel):
    """One OpenCode session row."""

    id: str
    project_id: str
    parent_id: str | None = None
    slug: str
    directory: str
    title: str
    version: str
    time_created: int
    time_updated: int


class OpenCloudMessageRecord(BaseModel):
    """One OpenCode message row with parsed payload."""

    id: str
    session_id: str
    time_created: int
    time_updated: int
    data: dict[str, Any]


class OpenCloudPartRecord(BaseModel):
    """One OpenCode part row with parsed payload."""

    id: str
    message_id: str
    session_id: str
    time_created: int
    time_updated: int
    data: dict[str, Any]


@runtime_checkable
class OpenCloudStore(Protocol):
    """Read OpenCloud/OpenCode sessions from the local SQLite store."""

    def list_sessions(self) -> list[OpenCloudSessionRecord]:
        """Return all discovered sessions, newest first."""
        ...

    def get_session(self, session_id: str) -> OpenCloudSessionRecord | None:
        """Return one session row by id."""
        ...

    def list_messages(self, session_id: str) -> list[OpenCloudMessageRecord]:
        """Return all messages for a session, oldest first."""
        ...

    def list_parts(self, session_id: str) -> list[OpenCloudPartRecord]:
        """Return all parts for a session, oldest first."""
        ...
