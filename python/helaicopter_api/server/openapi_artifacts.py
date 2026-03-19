"""Generate stable repo-local OpenAPI artifact files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from .config import Settings, load_settings
from .main import create_app


@dataclass(frozen=True)
class OpenApiArtifactOutputs:
    """Paths written by :func:`generate_openapi_artifacts`."""

    json_path: Path
    yaml_path: Path


def generate_openapi_artifacts(*, settings: Settings | None = None) -> OpenApiArtifactOutputs:
    """Write deterministic JSON and YAML OpenAPI artifacts under ``public/openapi``."""

    resolved_settings = settings or load_settings()
    artifact_settings = resolved_settings.openapi
    artifact_settings.artifacts_dir.mkdir(parents=True, exist_ok=True)

    application = create_app()
    schema = application.openapi()

    artifact_settings.json_path.write_text(
        json.dumps(schema, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    artifact_settings.yaml_path.write_text(
        yaml.safe_dump(schema, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )

    return OpenApiArtifactOutputs(
        json_path=artifact_settings.json_path,
        yaml_path=artifact_settings.yaml_path,
    )
