from __future__ import annotations

from pathlib import Path

import prefect
import pytest
import yaml
from pydantic import ValidationError

from oats.models import RepoConfig
from oats.repo_config import RepoConfigError, find_repo_config, load_repo_config
from oats.prefect.settings import (
    PrefectSettings,
    prefect_compose_file,
    prefect_env_example_file,
)


def _repo_config_data(*, prefect: dict[str, object] | None = None) -> dict[str, object]:
    data: dict[str, object] = {
        "repo": {
            "base_branch": "main",
            "worktree_dir": ".oats-worktrees",
            "default_concurrency": 3,
        },
        "agents": {
            "planner": "codex",
            "executor": "codex",
            "conflict_resolver": "claude",
            "merge_operator": "codex",
        },
        "agent": {
            "codex": {"command": "codex", "args": ["exec"]},
            "claude": {"command": "claude", "args": []},
        },
        "validation": {
            "commands": [
                "npm run lint",
                "uv run --group dev pytest -q",
            ],
            "fail_fast": True,
        },
        "git": {
            "task_branch_prefix": "oats/task/",
            "integration_branch_prefix": "oats/overnight/",
            "integration_branch_base": "main",
            "final_pr_target": "main",
            "auto_push": True,
            "auto_create_task_prs": True,
            "auto_merge_task_prs_into_integration": False,
            "auto_create_final_pr": True,
            "require_manual_final_review": True,
            "delete_worktree_on_success": True,
        },
    }
    if prefect is not None:
        data["prefect"] = prefect
    return data


def _repo_config_toml(
    *,
    validation_commands: tuple[str, ...] = ("npm run lint", "uv run --group dev pytest -q"),
    default_queue: str = "scheduled",
    default_tags: tuple[str, ...] = ("oats", "prefect"),
    default_schedule_enabled: bool = True,
    default_schedule_cron: str = "0 6 * * *",
    default_schedule_timezone: str = "Europe/Amsterdam",
) -> str:
    validation_commands_toml = ", ".join(f'"{command}"' for command in validation_commands)
    default_tags_toml = ", ".join(f'"{tag}"' for tag in default_tags)
    return f"""
[repo]
base_branch = "main"
worktree_dir = ".oats-worktrees"
default_concurrency = 3

[agents]
planner = "codex"
executor = "codex"
conflict_resolver = "claude"
merge_operator = "codex"

[agent.codex]
command = "codex"
args = ["exec"]

[agent.claude]
command = "claude"
args = []

[validation]
commands = [{validation_commands_toml}]
fail_fast = true

[prefect]
work_pool = "local-macos"
default_queue = "{default_queue}"
default_tags = [{default_tags_toml}]
default_task_retry_count = 2
default_task_timeout_seconds = 1800
default_schedule_enabled = {"true" if default_schedule_enabled else "false"}
default_schedule_cron = "{default_schedule_cron}"
default_schedule_timezone = "{default_schedule_timezone}"

[git]
task_branch_prefix = "oats/task/"
integration_branch_prefix = "oats/overnight/"
integration_branch_base = "main"
final_pr_target = "main"
auto_push = true
auto_create_task_prs = true
auto_merge_task_prs_into_integration = false
auto_create_final_pr = true
require_manual_final_review = true
delete_worktree_on_success = true
""".strip()


def _write_repo_config(tmp_path: Path, **kwargs: object) -> tuple[Path, Path]:
    repo_root = tmp_path / "repo"
    config_path = repo_root / ".oats" / "config.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(_repo_config_toml(**kwargs), encoding="utf-8")
    return repo_root, config_path


def test_prefect_settings_parse_api_url_from_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PREFECT_API_URL", "http://prefect.example.test/api")
    config = RepoConfig.model_validate(_repo_config_data())

    settings = PrefectSettings.from_repo_config(config, repo_root=tmp_path)

    assert settings.api_url == "http://prefect.example.test/api"


def test_prefect_settings_default_to_local_platform_values(tmp_path: Path) -> None:
    config = RepoConfig.model_validate(_repo_config_data())

    settings = PrefectSettings.from_repo_config(config, repo_root=tmp_path)

    assert settings.work_pool == "local-macos"
    assert settings.default_queue == "scheduled"
    assert settings.default_tags == []
    assert settings.default_task_retry_count == 0
    assert settings.default_task_timeout_seconds is None
    assert settings.default_validation_commands == [
        "npm run lint",
        "uv run --group dev pytest -q",
    ]
    assert settings.compose_file == prefect_compose_file(tmp_path)
    assert settings.env_example_file == prefect_env_example_file(tmp_path)


def test_repo_config_rejects_invalid_prefect_schedule_defaults() -> None:
    with pytest.raises(ValidationError):
        RepoConfig.model_validate(
            _repo_config_data(
                prefect={
                    "default_schedule_enabled": True,
                    "default_schedule_cron": "not-a-cron",
                    "default_schedule_timezone": "Europe/Amsterdam",
                }
            )
        )


def test_repo_config_allows_invalid_prefect_schedule_defaults_when_disabled() -> None:
    config = RepoConfig.model_validate(
        _repo_config_data(
            prefect={
                "default_schedule_enabled": False,
                "default_schedule_cron": "not-a-cron",
                "default_schedule_timezone": "Mars/Olympus",
            }
        )
    )

    assert config.prefect.default_schedule_enabled is False
    assert config.prefect.default_schedule_cron == "not-a-cron"
    assert config.prefect.default_schedule_timezone == "Mars/Olympus"


def test_load_repo_config_uses_temp_toml_fixture_for_prefect_settings(tmp_path: Path) -> None:
    repo_root, _ = _write_repo_config(
        tmp_path,
        validation_commands=("bin/validate-a", "bin/validate-b"),
        default_queue="overnight",
        default_tags=("nightly", "prefect"),
        default_schedule_enabled=True,
        default_schedule_cron="15 2 * * *",
        default_schedule_timezone="UTC",
    )
    config_path = find_repo_config(repo_root / "nested" / "path")
    config = load_repo_config(config_path)

    settings = PrefectSettings.from_repo_config(config, repo_root=repo_root)

    assert settings.default_validation_commands == [
        "bin/validate-a",
        "bin/validate-b",
    ]
    assert settings.default_queue == "overnight"
    assert settings.default_tags == ["nightly", "prefect"]
    assert settings.default_schedule_cron == "15 2 * * *"
    assert settings.default_schedule_timezone == "UTC"
    assert config.repo.worktree_dir == ".oats-worktrees"
    assert config.git.integration_branch_base == "main"


def test_load_repo_config_allows_invalid_prefect_schedule_when_disabled(tmp_path: Path) -> None:
    repo_root, _ = _write_repo_config(
        tmp_path,
        default_schedule_enabled=False,
        default_schedule_cron="not-a-cron",
        default_schedule_timezone="Mars/Olympus",
    )
    config_path = find_repo_config(repo_root / "nested" / "path")

    config = load_repo_config(config_path)

    assert config.prefect.default_schedule_enabled is False
    assert config.prefect.default_schedule_cron == "not-a-cron"
    assert config.prefect.default_schedule_timezone == "Mars/Olympus"


def test_load_repo_config_rejects_invalid_prefect_timezone_from_disk(tmp_path: Path) -> None:
    repo_root, _ = _write_repo_config(tmp_path, default_schedule_timezone="Mars/Olympus")
    config_path = find_repo_config(repo_root / "nested" / "path")

    with pytest.raises(RepoConfigError, match="Invalid timezone"):
        load_repo_config(config_path)


def test_prefect_settings_parse_schedule_and_routing_defaults_from_repo_config(
    tmp_path: Path,
) -> None:
    config = RepoConfig.model_validate(
        _repo_config_data(
            prefect={
                "work_pool": "local-macos",
                "default_queue": "overnight",
                "default_tags": ["oats", "prefect"],
                "default_task_retry_count": 2,
                "default_task_timeout_seconds": 1800,
                "default_schedule_enabled": True,
                "default_schedule_cron": "0 6 * * *",
                "default_schedule_timezone": "Europe/Amsterdam",
            }
        )
    )

    settings = PrefectSettings.from_repo_config(config, repo_root=tmp_path)

    assert config.repo.worktree_dir == ".oats-worktrees"
    assert config.git.integration_branch_base == "main"
    assert settings.work_pool == "local-macos"
    assert settings.default_queue == "overnight"
    assert settings.default_tags == ["oats", "prefect"]
    assert settings.default_task_retry_count == 2
    assert settings.default_task_timeout_seconds == 1800
    assert settings.default_schedule_enabled is True
    assert settings.default_schedule_cron == "0 6 * * *"
    assert settings.default_schedule_timezone == "Europe/Amsterdam"


def test_prefect_ops_assets_pin_the_installed_prefect_image_version() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    expected_image = f"prefecthq/prefect:{prefect.__version__}"
    compose_text = prefect_compose_file(repo_root).read_text(encoding="utf-8")
    env_text = prefect_env_example_file(repo_root).read_text(encoding="utf-8")

    assert f"PREFECT_IMAGE={expected_image}" in env_text
    assert f"${{PREFECT_IMAGE:-{expected_image}}}" in compose_text
    assert "3-latest" not in env_text
    assert "3-latest" not in compose_text


def test_prefect_compose_topology_separates_server_and_services() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    compose_data = yaml.safe_load(prefect_compose_file(repo_root).read_text(encoding="utf-8"))

    services = compose_data["services"]

    assert set(services) == {
        "postgres",
        "redis",
        "prefect-server",
        "prefect-services",
    }
    assert services["prefect-server"]["command"].endswith("--no-services")
    assert services["prefect-services"]["command"] == "prefect server services start"
    assert services["prefect-server"]["command"] != services["prefect-services"]["command"]
