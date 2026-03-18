from __future__ import annotations

from pathlib import Path
import tomllib

from pydantic import ValidationError

from oats.models import RepoConfig


DEFAULT_CONFIG_RELATIVE_PATH = Path(".oats/config.toml")


class RepoConfigError(RuntimeError):
    """Raised when repo configuration cannot be discovered or loaded."""


def find_repo_config(start: Path) -> Path:
    start_path = start.resolve()
    search_root = start_path if start_path.is_dir() else start_path.parent

    for candidate_dir in (search_root, *search_root.parents):
        config_path = candidate_dir / DEFAULT_CONFIG_RELATIVE_PATH
        if config_path.is_file():
            return config_path

    raise RepoConfigError(
        f"Could not find {DEFAULT_CONFIG_RELATIVE_PATH} starting from {search_root}"
    )


def load_repo_config(config_path: Path) -> RepoConfig:
    try:
        raw = tomllib.loads(config_path.read_text())
    except FileNotFoundError as exc:
        raise RepoConfigError(f"Config file not found: {config_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise RepoConfigError(f"Invalid TOML in {config_path}: {exc}") from exc

    try:
        return RepoConfig.model_validate(raw)
    except ValidationError as exc:
        raise RepoConfigError(f"Invalid repo config in {config_path}:\n{exc}") from exc
