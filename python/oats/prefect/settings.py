from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from oats.models import RepoConfig


DEFAULT_PREFECT_API_URL = "http://127.0.0.1:4200/api"


def prefect_compose_file(repo_root: Path) -> Path:
    return repo_root / "ops" / "prefect" / "docker-compose.yml"


def prefect_env_example_file(repo_root: Path) -> Path:
    return repo_root / "ops" / "prefect" / ".env.example"


class PrefectSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    api_url: str = Field(
        default=DEFAULT_PREFECT_API_URL,
        validation_alias="PREFECT_API_URL",
    )
    work_pool: str = "local-macos"
    default_queue: str = "scheduled"
    default_tags: list[str] = []
    default_validation_commands: list[str] = []
    default_task_retry_count: int = 0
    default_task_timeout_seconds: int | None = None
    default_schedule_enabled: bool = True
    default_schedule_cron: str | None = None
    default_schedule_timezone: str = "Europe/Amsterdam"
    compose_file: Path
    env_example_file: Path

    @classmethod
    def from_repo_config(cls, config: RepoConfig, repo_root: Path) -> "PrefectSettings":
        return cls(
            work_pool=config.prefect.work_pool,
            default_queue=config.prefect.default_queue,
            default_tags=list(config.prefect.default_tags),
            default_validation_commands=list(config.validation.commands),
            default_task_retry_count=config.prefect.default_task_retry_count,
            default_task_timeout_seconds=config.prefect.default_task_timeout_seconds,
            default_schedule_enabled=config.prefect.default_schedule_enabled,
            default_schedule_cron=config.prefect.default_schedule_cron,
            default_schedule_timezone=config.prefect.default_schedule_timezone,
            compose_file=prefect_compose_file(repo_root),
            env_example_file=prefect_env_example_file(repo_root),
        )
