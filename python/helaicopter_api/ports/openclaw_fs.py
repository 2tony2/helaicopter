"""Port protocols for OpenClaw filesystem session discovery."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class OpenClawSessionArtifact(BaseModel):
    """A raw OpenClaw session JSONL file discovered under ``~/.openclaw/agents``."""

    agent_id: str
    session_id: str
    path: str
    modified_at: float
    content: str


@runtime_checkable
class OpenClawStore(Protocol):
    """Read raw OpenClaw session artifacts from the local filesystem."""

    def list_session_artifacts(self) -> list[OpenClawSessionArtifact]:
        """Return all discovered OpenClaw session files, newest first."""
        ...

    def read_session_artifact(
        self,
        *,
        agent_id: str,
        session_id: str,
    ) -> OpenClawSessionArtifact | None:
        """Read one OpenClaw session artifact by agent and session identifier."""
        ...
