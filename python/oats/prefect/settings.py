from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_project_root() -> Path:
    return Path(__file__).resolve().parents[3]


class PrefectSettings(BaseSettings):
    """Focused Prefect settings for the local Oats rollout."""

    model_config = SettingsConfigDict(
        env_prefix="OATS_PREFECT_",
        extra="ignore",
    )

    project_root: Path = Field(
        default_factory=_default_project_root,
        description="Root of the helaicopter checkout that owns the Prefect assets.",
    )
    api_url: str = Field(
        default="http://127.0.0.1:4200/api",
        description="Prefect API URL for the local self-hosted control plane.",
    )
    work_pool: str = Field(
        default="local-macos",
        description="Default Prefect work pool for the host worker rollout.",
    )
    default_queue: str = Field(
        default="scheduled",
        description="Default Prefect queue for scheduled Oats runs.",
    )

    @property
    def prefect_ops_dir(self) -> Path:
        return self.project_root / "ops" / "prefect"

    @property
    def compose_file(self) -> Path:
        return self.prefect_ops_dir / "docker-compose.yml"

    @property
    def env_example_file(self) -> Path:
        return self.prefect_ops_dir / ".env.example"


def ensure_markdown_run_spec(path: Path) -> Path:
    if path.suffix.lower() != ".md":
        raise ValueError(
            f"Markdown run specs are the only supported input in this rollout: {path}"
        )
    return path


@lru_cache(maxsize=1)
def load_prefect_settings() -> PrefectSettings:
    return PrefectSettings()
