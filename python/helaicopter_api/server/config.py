"""Application configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime settings, resolved from env vars prefixed ``HELA_``."""

    model_config = {"env_prefix": "HELA_"}

    project_root: Path = Field(
        default_factory=lambda: Path.cwd(),
        description="Root of the helaicopter project checkout.",
    )
    oats_runtime_dir: Path | None = Field(
        default=None,
        description="Override for .oats/runtime/ directory. Defaults to <project_root>/.oats/runtime.",
    )
    claude_dir: Path = Field(
        default_factory=lambda: Path.home() / ".claude",
        description="Root of the Claude CLI data directory (typically ~/.claude).",
    )
    codex_dir: Path = Field(
        default_factory=lambda: Path.home() / ".codex",
        description="Root of the Codex CLI data directory (typically ~/.codex).",
    )
    debug: bool = False

    @property
    def runtime_dir(self) -> Path:
        if self.oats_runtime_dir is not None:
            return self.oats_runtime_dir
        return self.project_root / ".oats" / "runtime"

    @property
    def claude_projects_dir(self) -> Path:
        return self.claude_dir / "projects"

    @property
    def claude_plans_dir(self) -> Path:
        return self.claude_dir / "plans"

    @property
    def claude_history_file(self) -> Path:
        return self.claude_dir / "history.jsonl"

    @property
    def claude_tasks_dir(self) -> Path:
        return self.claude_dir / "tasks"

    @property
    def codex_sessions_dir(self) -> Path:
        return self.codex_dir / "sessions"

    @property
    def codex_history_file(self) -> Path:
        return self.codex_dir / "history.jsonl"

    @property
    def codex_sqlite_path(self) -> Path:
        return self.codex_dir / "state_5.sqlite"

    @property
    def app_sqlite_path(self) -> Path:
        return self.project_root / "public" / "database-artifacts" / "oltp" / "helaicopter_oltp.sqlite"
