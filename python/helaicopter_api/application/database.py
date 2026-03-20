"""Database status and refresh application logic."""

from __future__ import annotations

from typing import cast

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

from helaicopter_api.application.gateway import annotate_database_artifacts
from helaicopter_api.bootstrap.services import BackendServices, invalidate_backend_read_caches
from helaicopter_api.schema.database import DatabaseStatusResponse


SQLITE_NOTE = (
    "App-local metadata, refresh bookkeeping, evaluations, and historical "
    "detail tables."
)
DUCKDB_NOTE = (
    "Optional DuckDB inspection snapshot. It is not on the primary "
    "analytics serving path."
)


class DatabaseOperationError(RuntimeError):
    def __init__(self, message: str, *, payload: DatabaseStatusResponse | None = None) -> None:
        super().__init__(message)
        self.payload = payload


@validate_call(config=ConfigDict(strict=True), validate_return=True)
def read_database_status(services: InstanceOf[BackendServices]) -> DatabaseStatusResponse:
    """Return the current database status, bootstrapping on first read.

    If the persisted status payload is complete, it is returned immediately
    after annotation. Otherwise a forced refresh is triggered, caches are
    invalidated, and the result is coerced to a ``DatabaseStatusResponse``.

    Args:
        services: Initialised backend services used to access settings and
            invalidate read caches.

    Returns:
        Current ``DatabaseStatusResponse`` describing database availability,
        health, and table inventory.

    Raises:
        DatabaseOperationError: If the bootstrap refresh fails; the exception
            carries the latest known status payload in its ``payload`` attribute.
    """
    settings = _service_settings_or_none(services)
    payload = parse_status_payload(_load_status_with_optional_settings(settings))
    if payload is not None and _status_payload_is_complete(payload):
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
    """Run the backend-owned refresh flow and invalidate backend caches.

    Delegates to the underlying ``run_refresh`` utility with the supplied
    parameters, invalidates all backend read caches on completion, and
    returns the updated database status.

    Args:
        services: Initialised backend services used to access settings and
            invalidate read caches.
        force: When ``True``, the refresh runs even if the existing data is
            not yet stale.
        trigger: Human-readable label identifying the call-site (e.g.
            ``"manual"``, ``"schedule"``).
        stale_after_seconds: Age threshold in seconds beyond which cached
            data is considered stale and a refresh is warranted.

    Returns:
        Updated ``DatabaseStatusResponse`` after the refresh completes.

    Raises:
        DatabaseOperationError: If the refresh fails; the exception carries
            the latest known status payload in its ``payload`` attribute.
    """
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
    normalized = payload.copy()
    normalized.setdefault("refreshIntervalMinutes", 360)
    normalized.setdefault("runtime", _fallback_runtime_surface())
    normalized.setdefault("databases", _fallback_databases_surface(settings))
    normalized["databases"] = cast(
        DatabaseArtifactsPayload,
        annotate_database_artifacts(normalized.get("databases")),
    )
    return DatabaseStatusResponse.model_validate(normalized)


def _status_payload_is_complete(payload: DatabaseStatusPayload | None) -> bool:
    if payload is None:
        return False
    runtime = payload.get("runtime")
    databases = payload.get("databases") or {}
    return bool(
        runtime
        and databases.get("frontendCache")
        and databases.get("sqlite")
        and databases.get("duckdb")
        and databases.get("prefectPostgres")
    )


def _fallback_runtime_surface() -> DatabaseRuntimePayload:
    return {
        "analyticsReadBackend": "duckdb",
        "conversationSummaryReadBackend": "legacy",
    }


def _fallback_databases_surface(
    settings: Settings | None = None,
) -> DatabaseArtifactsPayload:
    database_settings = get_database_settings(settings)
    sqlite = database_settings.sqlite
    duckdb_settings = database_settings.duckdb
    sqlite_exists = sqlite.path.exists()
    duckdb_exists = duckdb_settings.path.exists()
    return {
        "frontendCache": {
            "key": "frontend_cache",
            "label": "Frontend Short-Term Cache",
            "engine": "In-process memory",
            "role": "cache",
            "availability": "ready",
            "health": "healthy",
            "operationalStatus": "Backend read cache available for dashboard and conversation reads.",
            "note": "Short-lived backend cache for active UI polling paths.",
            "error": None,
            "path": None,
            "target": "BackendServices.cache",
            "publicPath": None,
            "docsUrl": None,
            "tableCount": 0,
            "sizeBytes": None,
            "sizeDisplay": None,
            "inventorySummary": "Ephemeral in-memory cache",
            "load": [],
            "tables": [],
        },
        "sqlite": {
            "key": sqlite.key,
            "label": sqlite.label,
            "engine": sqlite.engine,
            "role": "metadata",
            "availability": "ready" if sqlite_exists else "missing",
            "health": "healthy" if sqlite_exists else "missing",
            "operationalStatus": (
                "SQLite metadata store available."
                if sqlite_exists
                else "SQLite metadata store has not been created yet."
            ),
            "note": SQLITE_NOTE,
            "error": None,
            "path": str(sqlite.path),
            "target": None,
            "publicPath": sqlite.public_path,
            "docsUrl": sqlite.docs_url,
            "tableCount": 0,
            "sizeBytes": None,
            "sizeDisplay": None,
            "inventorySummary": "No table inventory recorded yet",
            "load": [],
            "tables": [],
        },
        "duckdb": {
            "key": duckdb_settings.key,
            "label": duckdb_settings.label,
            "engine": duckdb_settings.engine,
            "role": "inspection",
            "availability": "ready" if duckdb_exists else "missing",
            "health": "healthy" if duckdb_exists else "missing",
            "operationalStatus": (
                "DuckDB inspection snapshot available."
                if duckdb_exists
                else "DuckDB inspection snapshot has not been generated yet."
            ),
            "note": DUCKDB_NOTE,
            "error": None,
            "path": str(duckdb_settings.path),
            "target": None,
            "publicPath": duckdb_settings.public_path,
            "docsUrl": duckdb_settings.docs_url,
            "tableCount": 0,
            "sizeBytes": None,
            "sizeDisplay": None,
            "inventorySummary": "No table inventory recorded yet",
            "load": [],
            "tables": [],
        },
        "prefectPostgres": {
            "key": "prefect_postgres",
            "label": "Prefect Postgres",
            "engine": "Postgres",
            "role": "orchestration",
            "availability": "ready",
            "health": "healthy",
            "operationalStatus": "Prefect control-plane database target configured.",
            "note": "Backing store for the self-hosted Prefect API and services stack.",
            "error": None,
            "path": None,
            "target": "postgresql://prefect@127.0.0.1:5432/prefect",
            "publicPath": None,
            "docsUrl": None,
            "tableCount": 0,
            "sizeBytes": None,
            "sizeDisplay": None,
            "inventorySummary": "Catalog visibility is managed through Prefect/Postgres.",
            "load": [],
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
) -> DatabaseStatusPayload:
    if settings is None:
        return run_refresh(force=force, trigger=trigger, stale_after_seconds=stale_after_seconds)
    return run_refresh(
        force=force,
        trigger=trigger,
        stale_after_seconds=stale_after_seconds,
        settings=settings,
    )


def _load_status_with_optional_settings(settings: Settings | None) -> object | None:
    if settings is None:
        return load_status()
    return load_status(settings)
