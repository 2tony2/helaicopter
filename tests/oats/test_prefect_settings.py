from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from oats.prefect.settings import PrefectSettings, ensure_markdown_run_spec, load_prefect_settings


def test_prefect_dependency_is_declared_and_settings_module_is_importable() -> None:
    pyproject = tomllib.loads((Path.cwd() / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    assert any(dependency.startswith("prefect>=") for dependency in dependencies)
    assert PrefectSettings.__module__ == "oats.prefect.settings"


def test_load_prefect_settings_uses_env_api_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OATS_PREFECT_API_URL", "http://localhost:4310/api")
    load_prefect_settings.cache_clear()

    settings = load_prefect_settings()

    assert settings.api_url == "http://localhost:4310/api"


def test_prefect_settings_expose_default_pool_queue_and_assets() -> None:
    load_prefect_settings.cache_clear()
    settings = load_prefect_settings()

    assert settings.work_pool == "local-macos"
    assert settings.default_queue == "scheduled"
    assert settings.compose_file == Path.cwd() / "ops" / "prefect" / "docker-compose.yml"
    assert settings.env_example_file == Path.cwd() / "ops" / "prefect" / ".env.example"
    assert settings.compose_file.is_file()
    assert settings.env_example_file.is_file()


def test_prefect_settings_allow_repo_root_override_for_asset_discovery(tmp_path: Path) -> None:
    settings = PrefectSettings(project_root=tmp_path)

    assert settings.compose_file == tmp_path / "ops" / "prefect" / "docker-compose.yml"
    assert settings.env_example_file == tmp_path / "ops" / "prefect" / ".env.example"


def test_prefect_settings_reject_non_markdown_run_specs() -> None:
    with pytest.raises(ValueError, match="Markdown"):
        ensure_markdown_run_spec(Path("runs/local-platform-foundation.yaml"))


def test_prefect_settings_accept_markdown_run_specs() -> None:
    path = Path("runs/local-platform-foundation.md")

    assert ensure_markdown_run_spec(path) == path
