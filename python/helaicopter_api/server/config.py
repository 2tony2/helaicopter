"""Application configuration via pydantic-settings."""

from __future__ import annotations

from functools import cached_property
from pathlib import Path
import subprocess

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from helaicopter_api.server.dev_instance import build_checkout_instance


def _default_project_root() -> Path:
    cwd = Path.cwd().resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return cwd

    if result.returncode != 0:
        return cwd

    raw_path = result.stdout.strip()
    if not raw_path:
        return cwd

    git_common_dir = Path(raw_path)
    if not git_common_dir.is_absolute():
        git_common_dir = (cwd / git_common_dir).resolve()
    else:
        git_common_dir = git_common_dir.resolve()

    if git_common_dir.name == ".git":
        return git_common_dir.parent

    return cwd


class CliSettings(BaseModel):
    """Filesystem roots owned by local Claude and Codex integrations."""

    claude_dir: Path
    codex_dir: Path
    openclaw_dir: Path
    opencloud_dir: Path

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
    def openclaw_agents_dir(self) -> Path:
        return self.openclaw_dir / "agents"

    @property
    def openclaw_agent_sessions_glob(self) -> str:
        return str(self.openclaw_agents_dir / "*" / "sessions")

    @property
    def opencloud_sqlite_path(self) -> Path:
        return self.opencloud_dir / "opencode.db"


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
        default_factory=_default_project_root,
        description="Root of the helaicopter project checkout.",
    )
    checkout_runtime_root: Path | None = Field(
        default=None,
        description="Override for checkout-local generated runtime/artifact files.",
    )
    api_port_override: int | None = Field(
        default=None,
        validation_alias="HELA_API_PORT",
        description="Override for the checkout-local FastAPI dev port.",
    )
    web_port_override: int | None = Field(
        default=None,
        validation_alias="HELA_WEB_PORT",
        description="Override for the checkout-local Next.js dev port.",
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
    openclaw_dir: Path = Field(
        default_factory=lambda: Path.home() / ".openclaw",
        description="Root of the OpenClaw data directory (typically ~/.openclaw).",
    )
    opencloud_dir: Path = Field(
        default_factory=lambda: Path.home() / ".local" / "share" / "opencode",
        description="Root of the OpenCode runtime data directory that backs the OpenCloud provider.",
    )
    debug: bool = False

    @cached_property
    def checkout_instance(self):
        return build_checkout_instance(self.project_root)

    @cached_property
    def cli(self) -> CliSettings:
        return CliSettings(
            claude_dir=self.claude_dir,
            codex_dir=self.codex_dir,
            openclaw_dir=self.openclaw_dir,
            opencloud_dir=self.opencloud_dir,
        )

    @cached_property
    def database(self) -> DatabaseSettings:
        runtime_root = self.checkout_runtime_root or (self.project_root / ".helaicopter")
        public_dir = self.project_root / "public"
        artifacts_dir = public_dir / "database-artifacts"
        schema_docs_dir = public_dir / "database-schemas"
        runtime_dir = runtime_root / "database-runtime"
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
    def api_port(self) -> int:
        return self.api_port_override or self.checkout_instance.api_port

    @property
    def web_port(self) -> int:
        return self.web_port_override or self.checkout_instance.web_port

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
    def openclaw_agents_dir(self) -> Path:
        return self.cli.openclaw_agents_dir

    @property
    def openclaw_agent_sessions_glob(self) -> str:
        return self.cli.openclaw_agent_sessions_glob

    @property
    def opencloud_sqlite_path(self) -> Path:
        return self.cli.opencloud_sqlite_path

    @property
    def app_sqlite_path(self) -> Path:
        return self.database.sqlite.path


def load_settings() -> Settings:
    """Load backend settings from the current process environment."""

    return Settings()
