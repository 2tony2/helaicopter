"""Application configuration via pydantic-settings."""

from __future__ import annotations

from functools import cached_property
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CliSettings(BaseModel):
    """Filesystem roots owned by local Claude and Codex integrations."""

    claude_dir: Path
    codex_dir: Path

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


class DatabaseArtifactSettings(BaseModel):
    """Shared path contract for one backend-owned database artifact."""

    key: str
    label: str
    engine: str
    sqlalchemy_driver: str
    path: Path
    docs_dir: Path
    public_path: str
    docs_url: str

    @property
    def sqlalchemy_url(self) -> str:
        return f"{self.sqlalchemy_driver}:///{self.path}"

    @property
    def catalog_name(self) -> str:
        return self.path.stem


class DatabaseSettings(BaseModel):
    """Paths and artifacts owned by backend refresh and migration tooling."""

    runtime_dir: Path
    tools_dir: Path
    lock_file: Path
    status_file: Path
    public_dir: Path
    artifacts_dir: Path
    schema_docs_dir: Path
    sqlite: DatabaseArtifactSettings
    duckdb: DatabaseArtifactSettings

    @property
    def legacy_duckdb(self) -> DatabaseArtifactSettings:
        """Compatibility alias for callers that still use the old name."""
        return self.duckdb


class PrefectApiSettings(BaseModel):
    """Backend-owned Prefect API connection settings."""

    api_url: str
    timeout_seconds: float = 30.0


class OpenApiArtifactSettings(BaseModel):
    """Stable repo-local OpenAPI artifact output settings."""

    artifacts_dir: Path
    json_path: Path
    yaml_path: Path
    json_url: str
    yaml_url: str


class Settings(BaseSettings):
    """Runtime settings, resolved from env vars prefixed ``HELA_``."""

    model_config = SettingsConfigDict(env_prefix="HELA_")

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
    prefect_api_url: str = Field(
        default="http://127.0.0.1:4200/api",
        description="Base URL for the Prefect API proxied by the backend.",
    )
    prefect_api_timeout_seconds: float = Field(
        default=30.0,
        description="Timeout for Prefect API requests made by the backend.",
    )
    debug: bool = False

    @cached_property
    def cli(self) -> CliSettings:
        return CliSettings(
            claude_dir=self.claude_dir,
            codex_dir=self.codex_dir,
        )

    @cached_property
    def database(self) -> DatabaseSettings:
        public_dir = self.project_root / "public"
        artifacts_dir = public_dir / "database-artifacts"
        schema_docs_dir = public_dir / "database-schemas"
        runtime_dir = self.project_root / "var" / "database-runtime"
        return DatabaseSettings(
            runtime_dir=runtime_dir,
            tools_dir=runtime_dir / "tools",
            lock_file=runtime_dir / "refresh.lock",
            status_file=runtime_dir / "status.json",
            public_dir=public_dir,
            artifacts_dir=artifacts_dir,
            schema_docs_dir=schema_docs_dir,
            sqlite=DatabaseArtifactSettings(
                key="sqlite",
                label="SQLite Metadata Store",
                engine="SQLite",
                sqlalchemy_driver="sqlite",
                path=artifacts_dir / "oltp" / "helaicopter_oltp.sqlite",
                docs_dir=schema_docs_dir / "oltp",
                public_path="/database-artifacts/oltp/helaicopter_oltp.sqlite",
                docs_url="/database-schemas/oltp/index.html",
            ),
            duckdb=DatabaseArtifactSettings(
                key="duckdb",
                label="DuckDB Inspection Snapshot",
                engine="DuckDB",
                sqlalchemy_driver="duckdb",
                path=artifacts_dir / "olap" / "helaicopter_olap.duckdb",
                docs_dir=schema_docs_dir / "olap",
                public_path="/database-artifacts/olap/helaicopter_olap.duckdb",
                docs_url="/database-schemas/olap/index.html",
            ),
        )

    @cached_property
    def prefect(self) -> PrefectApiSettings:
        return PrefectApiSettings(
            api_url=self.prefect_api_url,
            timeout_seconds=self.prefect_api_timeout_seconds,
        )

    @cached_property
    def openapi(self) -> OpenApiArtifactSettings:
        artifacts_dir = self.project_root / "public" / "openapi"
        return OpenApiArtifactSettings(
            artifacts_dir=artifacts_dir,
            json_path=artifacts_dir / "helaicopter-api.json",
            yaml_path=artifacts_dir / "helaicopter-api.yaml",
            json_url="/openapi/helaicopter-api.json",
            yaml_url="/openapi/helaicopter-api.yaml",
        )

    @property
    def runtime_dir(self) -> Path:
        if self.oats_runtime_dir is not None:
            return self.oats_runtime_dir
        return self.project_root / ".oats" / "runtime"

    @property
    def claude_projects_dir(self) -> Path:
        return self.cli.claude_projects_dir

    @property
    def claude_plans_dir(self) -> Path:
        return self.cli.claude_plans_dir

    @property
    def claude_history_file(self) -> Path:
        return self.cli.claude_history_file

    @property
    def claude_tasks_dir(self) -> Path:
        return self.cli.claude_tasks_dir

    @property
    def codex_sessions_dir(self) -> Path:
        return self.cli.codex_sessions_dir

    @property
    def codex_history_file(self) -> Path:
        return self.cli.codex_history_file

    @property
    def codex_sqlite_path(self) -> Path:
        return self.cli.codex_sqlite_path

    @property
    def app_sqlite_path(self) -> Path:
        return self.database.sqlite.path


def load_settings() -> Settings:
    """Load backend settings from the current process environment."""

    return Settings()
