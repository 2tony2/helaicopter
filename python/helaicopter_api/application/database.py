"""Database status and refresh application logic."""

from __future__ import annotations

from typing import Any

from helaicopter_db.refresh import run_refresh
from helaicopter_db.settings import DUCKDB_LEGACY_ARTIFACT, SQLITE_ARTIFACT
from helaicopter_db.status import load_status

from helaicopter_api.bootstrap.services import BackendServices, invalidate_backend_read_caches
from helaicopter_api.schema.database import DatabaseStatusResponse


SQLITE_NOTE = (
    "App-local metadata, refresh bookkeeping, evaluations, and historical "
    "detail tables."
)
LEGACY_DUCKDB_NOTE = (
    "Legacy compatibility/debug artifact only. It is not on the primary "
    "analytics serving path."
)


class DatabaseOperationError(RuntimeError):
    def __init__(self, message: str, *, payload: DatabaseStatusResponse | None = None) -> None:
        super().__init__(message)
        self.payload = payload


def read_database_status(services: BackendServices) -> DatabaseStatusResponse:
    """Return the current database status, bootstrapping on first read."""
    payload = load_status()
    if _status_payload_is_complete(payload):
        return _coerce_status_payload(payload)

    try:
        refreshed = run_refresh(force=True, trigger="bootstrap", stale_after_seconds=21_600)
    except Exception as exc:
        invalidate_backend_read_caches(services)
        raise DatabaseOperationError(
            str(exc),
            payload=_coerce_optional_status_payload(load_status()),
        ) from exc

    invalidate_backend_read_caches(services)
    return _coerce_status_payload(refreshed)


def trigger_database_refresh(
    services: BackendServices,
    *,
    force: bool,
    trigger: str,
    stale_after_seconds: int,
) -> DatabaseStatusResponse:
    """Run the backend-owned refresh flow and invalidate backend caches."""
    try:
        payload = run_refresh(
            force=force,
            trigger=trigger,
            stale_after_seconds=stale_after_seconds,
        )
    except Exception as exc:
        invalidate_backend_read_caches(services)
        raise DatabaseOperationError(
            str(exc),
            payload=_coerce_optional_status_payload(load_status()),
        ) from exc

    invalidate_backend_read_caches(services)
    return _coerce_status_payload(payload)


def _coerce_optional_status_payload(payload: dict[str, Any] | None) -> DatabaseStatusResponse | None:
    if payload is None:
        return None
    return _coerce_status_payload(payload)


def _coerce_status_payload(payload: dict[str, Any]) -> DatabaseStatusResponse:
    normalized = dict(payload)
    normalized.setdefault("refreshIntervalMinutes", 360)
    normalized.setdefault("runtime", _fallback_runtime_surface())
    normalized.setdefault("databases", _fallback_databases_surface())
    return DatabaseStatusResponse.model_validate(normalized)


def _status_payload_is_complete(payload: dict[str, Any] | None) -> bool:
    if payload is None:
        return False
    runtime = payload.get("runtime")
    databases = payload.get("databases") or {}
    return bool(runtime and databases.get("sqlite") and databases.get("legacyDuckdb"))


def _fallback_runtime_surface() -> dict[str, str]:
    return {
        "analyticsReadBackend": "legacy",
        "conversationSummaryReadBackend": "legacy",
    }


def _fallback_databases_surface() -> dict[str, Any]:
    sqlite_exists = SQLITE_ARTIFACT.path.exists()
    legacy_exists = DUCKDB_LEGACY_ARTIFACT.path.exists()
    return {
        "sqlite": {
            "key": SQLITE_ARTIFACT.key,
            "label": SQLITE_ARTIFACT.label,
            "engine": SQLITE_ARTIFACT.engine,
            "role": "metadata",
            "availability": "ready" if sqlite_exists else "missing",
            "note": SQLITE_NOTE,
            "error": None,
            "path": str(SQLITE_ARTIFACT.path),
            "target": None,
            "publicPath": SQLITE_ARTIFACT.public_path,
            "docsUrl": SQLITE_ARTIFACT.docs_url,
            "tableCount": 0,
            "tables": [],
        },
        "legacyDuckdb": {
            "key": DUCKDB_LEGACY_ARTIFACT.key,
            "label": DUCKDB_LEGACY_ARTIFACT.label,
            "engine": DUCKDB_LEGACY_ARTIFACT.engine,
            "role": "legacy_debug",
            "availability": "ready" if legacy_exists else "missing",
            "note": LEGACY_DUCKDB_NOTE,
            "error": None,
            "path": str(DUCKDB_LEGACY_ARTIFACT.path),
            "target": None,
            "publicPath": DUCKDB_LEGACY_ARTIFACT.public_path,
            "docsUrl": DUCKDB_LEGACY_ARTIFACT.docs_url,
            "tableCount": 0,
            "tables": [],
        },
    }
