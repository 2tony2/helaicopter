"""Database status and refresh application logic."""

from __future__ import annotations

from pydantic import ConfigDict, InstanceOf, validate_call

from helaicopter_api.server.config import Settings
from helaicopter_db.refresh import run_refresh
from helaicopter_db.settings import get_database_settings
from helaicopter_db.status import (
    DatabaseArtifactsPayload,
    DatabaseRuntimePayload,
    DatabaseStatusPayload,
    load_status,
    parse_status_payload,
)

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


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def read_database_status(services: InstanceOf[BackendServices]) -> DatabaseStatusResponse:
    """Return the current database status, bootstrapping on first read."""
    settings = _service_settings_or_none(services)
    payload = parse_status_payload(_load_status_with_optional_settings(settings))
    if _status_payload_is_complete(payload):
        return _coerce_status_payload(payload, settings)

    try:
        refreshed = _run_refresh_with_optional_settings(
            force=True,
            trigger="bootstrap",
            stale_after_seconds=21_600,
            settings=settings,
        )
    except Exception as exc:
        invalidate_backend_read_caches(services)
        raise DatabaseOperationError(
            str(exc),
            payload=_coerce_optional_status_payload(_load_status_with_optional_settings(settings), settings),
        ) from exc

    invalidate_backend_read_caches(services)
    return _coerce_optional_status_payload(refreshed, settings) or DatabaseStatusResponse.model_validate(
        {
            "status": "failed",
            "runtime": _fallback_runtime_surface(),
            "databases": _fallback_databases_surface(settings),
        }
    )


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def trigger_database_refresh(
    services: InstanceOf[BackendServices],
    *,
    force: bool,
    trigger: str,
    stale_after_seconds: int,
) -> DatabaseStatusResponse:
    """Run the backend-owned refresh flow and invalidate backend caches."""
    settings = _service_settings_or_none(services)
    try:
        payload = _run_refresh_with_optional_settings(
            force=force,
            trigger=trigger,
            stale_after_seconds=stale_after_seconds,
            settings=settings,
        )
    except Exception as exc:
        invalidate_backend_read_caches(services)
        raise DatabaseOperationError(
            str(exc),
            payload=_coerce_optional_status_payload(_load_status_with_optional_settings(settings), settings),
        ) from exc

    invalidate_backend_read_caches(services)
    return _coerce_optional_status_payload(payload, settings) or DatabaseStatusResponse.model_validate(
        {
            "status": "failed",
            "runtime": _fallback_runtime_surface(),
            "databases": _fallback_databases_surface(settings),
        }
    )


def _coerce_optional_status_payload(
    payload: object | None,
    settings: Settings | None = None,
) -> DatabaseStatusResponse | None:
    typed_payload = parse_status_payload(payload)
    if typed_payload is None:
        return None
    return _coerce_status_payload(typed_payload, settings)


def _coerce_status_payload(
    payload: DatabaseStatusPayload,
    settings: Settings | None = None,
) -> DatabaseStatusResponse:
    normalized: DatabaseStatusPayload = dict(payload)
    normalized.setdefault("refreshIntervalMinutes", 360)
    normalized.setdefault("runtime", _fallback_runtime_surface())
    normalized.setdefault("databases", _fallback_databases_surface(settings))
    return DatabaseStatusResponse.model_validate(normalized)


def _status_payload_is_complete(payload: DatabaseStatusPayload | None) -> bool:
    if payload is None:
        return False
    runtime = payload.get("runtime")
    databases = payload.get("databases") or {}
    return bool(runtime and databases.get("sqlite") and databases.get("legacyDuckdb"))


def _fallback_runtime_surface() -> DatabaseRuntimePayload:
    return {
        "analyticsReadBackend": "legacy",
        "conversationSummaryReadBackend": "legacy",
    }


def _fallback_databases_surface(
    settings: Settings | None = None,
) -> DatabaseArtifactsPayload:
    database_settings = get_database_settings(settings)
    sqlite = database_settings.sqlite
    legacy_duckdb = database_settings.legacy_duckdb
    sqlite_exists = sqlite.path.exists()
    legacy_exists = legacy_duckdb.path.exists()
    return {
        "sqlite": {
            "key": sqlite.key,
            "label": sqlite.label,
            "engine": sqlite.engine,
            "role": "metadata",
            "availability": "ready" if sqlite_exists else "missing",
            "note": SQLITE_NOTE,
            "error": None,
            "path": str(sqlite.path),
            "target": None,
            "publicPath": sqlite.public_path,
            "docsUrl": sqlite.docs_url,
            "tableCount": 0,
            "tables": [],
        },
        "legacyDuckdb": {
            "key": legacy_duckdb.key,
            "label": legacy_duckdb.label,
            "engine": legacy_duckdb.engine,
            "role": "legacy_debug",
            "availability": "ready" if legacy_exists else "missing",
            "note": LEGACY_DUCKDB_NOTE,
            "error": None,
            "path": str(legacy_duckdb.path),
            "target": None,
            "publicPath": legacy_duckdb.public_path,
            "docsUrl": legacy_duckdb.docs_url,
            "tableCount": 0,
            "tables": [],
        },
    }


def _service_settings_or_none(services: BackendServices) -> Settings | None:
    return getattr(services, "settings", None)


def _run_refresh_with_optional_settings(
    *,
    force: bool,
    trigger: str,
    stale_after_seconds: int,
    settings: Settings | None,
) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "force": force,
        "trigger": trigger,
        "stale_after_seconds": stale_after_seconds,
    }
    if settings is not None:
        kwargs["settings"] = settings
    return run_refresh(**kwargs)


def _load_status_with_optional_settings(settings: Settings | None) -> object | None:
    if settings is None:
        return load_status()
    return load_status(settings)
