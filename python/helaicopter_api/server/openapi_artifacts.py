"""Generate stable repo-local OpenAPI artifact files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

from .config import Settings, load_settings
from .main import create_app


@dataclass(frozen=True)
class OpenApiArtifactOutputs:
    """Paths written by :func:`generate_openapi_artifacts`."""

    json_path: Path
    yaml_path: Path


FRONTEND_APP_PATHS = (
    "/analytics",
    "/conversation-dags",
    "/conversations",
    "/conversations/by-ref/{conversation_ref}",
    "/conversations/{project_path}/{session_id}",
    "/conversations/{project_path}/{session_id}/dag",
    "/conversations/{project_path}/{session_id}/evaluations",
    "/databases/refresh",
    "/databases/status",
    "/evaluation-prompts",
    "/evaluation-prompts/{prompt_id}",
    "/history",
    "/plans",
    "/plans/{slug}",
    "/projects",
    "/subagents/{project_path}/{session_id}/{agent_id}",
    "/subscription-settings",
    "/tasks/{session_id}",
)


def _build_surface_schema(
    schema: dict[str, Any],
    *,
    title: str,
    description: str,
    include_path: Callable[[str], bool],
) -> dict[str, Any]:
    surface_schema = dict(schema)
    surface_schema["info"] = {
        **schema.get("info", {}),
        "title": title,
        "description": description,
    }
    surface_schema["paths"] = {
        path: operation
        for path, operation in schema.get("paths", {}).items()
        if include_path(path)
    }
    return surface_schema


def _write_json_artifact(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def generate_openapi_artifacts(*, settings: Settings | None = None) -> OpenApiArtifactOutputs:
    """Write deterministic JSON and YAML OpenAPI artifacts under ``public/openapi``."""

    resolved_settings = settings or load_settings()
    artifact_settings = resolved_settings.openapi
    artifact_settings.artifacts_dir.mkdir(parents=True, exist_ok=True)

    application = create_app()
    schema = application.openapi()

    _write_json_artifact(
        artifact_settings.json_path,
        schema,
    )
    artifact_settings.yaml_path.write_text(
        yaml.safe_dump(schema, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )

    _write_json_artifact(
        artifact_settings.artifacts_dir / "helaicopter-frontend-app-api.json",
        _build_surface_schema(
            schema,
            title="Helaicopter Frontend App API",
            description=(
                "Stable filtered view of the backend routes consumed by the Next.js app, "
                "excluding internal ops and dedicated orchestration surfaces."
            ),
            include_path=lambda path: path in FRONTEND_APP_PATHS,
        ),
    )
    _write_json_artifact(
        artifact_settings.artifacts_dir / "helaicopter-oats-orchestration-api.json",
        _build_surface_schema(
            schema,
            title="Helaicopter OATS Orchestration API",
            description="Stable filtered view of the legacy repo-local OATS orchestration routes.",
            include_path=lambda path: path == "/orchestration/oats",
        ),
    )
    return OpenApiArtifactOutputs(
        json_path=artifact_settings.json_path,
        yaml_path=artifact_settings.yaml_path,
    )
