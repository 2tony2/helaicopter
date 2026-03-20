from __future__ import annotations

import json
import os
from typing import TypedDict

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import inspect, text
from helaicopter_api.server.config import Settings
from helaicopter_domain.vocab import DatabaseRefreshStatus, RuntimeReadBackend

from .db import create_oltp_engine
from .settings import get_database_settings


class DatabaseColumnPayload(TypedDict):
    name: str
    type: str
    nullable: bool
    defaultValue: str | None
    isPrimaryKey: bool
    references: str | None


class DatabaseTablePayload(TypedDict, total=False):
    name: str
    rowCount: int
    sizeBytes: int | None
    sizeDisplay: str | None
    columns: list[DatabaseColumnPayload]


class DatabaseRuntimePayload(TypedDict):
    analyticsReadBackend: RuntimeReadBackend
    conversationSummaryReadBackend: RuntimeReadBackend


class DatabaseArtifactPayload(TypedDict, total=False):
    key: str
    label: str
    engine: str
    role: str
    availability: str
    health: str
    operationalStatus: str
    note: str
    error: str | None
    path: str | None
    target: str | None
    publicPath: str | None
    docsUrl: str | None
    tableCount: int
    sizeBytes: int | None
    sizeDisplay: str | None
    inventorySummary: str
    load: list[object]
    tables: list[DatabaseTablePayload]


class DatabaseArtifactsPayload(TypedDict, total=False):
    frontendCache: DatabaseArtifactPayload
    sqlite: DatabaseArtifactPayload
    prefectPostgres: DatabaseArtifactPayload
    duckdb: DatabaseArtifactPayload


class DatabaseStatusPayload(TypedDict, total=False):
    status: DatabaseRefreshStatus
    trigger: str
    startedAt: str
    finishedAt: str | None
    durationMs: int | float | None
    error: str | None
    lastSuccessfulRefreshAt: str | None
    idempotencyKey: str | None
    scopeLabel: str
    windowDays: int
    windowStart: str | None
    windowEnd: str | None
    sourceConversationCount: int
    refreshIntervalMinutes: int
    runtime: DatabaseRuntimePayload
    databases: DatabaseArtifactsPayload


_STATUS_PAYLOAD_ADAPTER = TypeAdapter(DatabaseStatusPayload)


def _format_size(size_bytes: int | None) -> str | None:
    if size_bytes is None:
        return None
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"


def _path_size(path) -> int | None:
    try:
        if path.exists():
            return path.stat().st_size
    except OSError:
        return None
    return None


def _prefect_postgres_target() -> str:
    user = os.getenv("PREFECT_POSTGRES_USER", "prefect")
    password = os.getenv("PREFECT_POSTGRES_PASSWORD")
    host = os.getenv("PREFECT_POSTGRES_HOST", "127.0.0.1")
    port = os.getenv("PREFECT_POSTGRES_PORT", "5432")
    database = os.getenv("PREFECT_POSTGRES_DB", "prefect")
    auth = user if not password else f"{user}:***"
    return f"postgresql://{auth}@{host}:{port}/{database}"


def _sqlite_table_summaries(engine) -> list[DatabaseTablePayload]:
    inspector = inspect(engine)
    tables: list[DatabaseTablePayload] = []

    for table_name in sorted(inspector.get_table_names()):
        pk_columns = set(inspector.get_pk_constraint(table_name).get("constrained_columns", []))
        fk_map: dict[str, str] = {}
        for foreign_key in inspector.get_foreign_keys(table_name):
            referred_table = foreign_key.get("referred_table")
            referred_columns = foreign_key.get("referred_columns") or []
            for column_name in foreign_key.get("constrained_columns") or []:
                fk_map[column_name] = f"{referred_table}({', '.join(referred_columns)})"

        columns: list[DatabaseColumnPayload] = []
        for column in inspector.get_columns(table_name):
            default_value = column.get("default")
            columns.append(
                {
                    "name": column["name"],
                    "type": str(column["type"]),
                    "nullable": bool(column.get("nullable", True)),
                    "defaultValue": None if default_value is None else str(default_value),
                    "isPrimaryKey": column["name"] in pk_columns,
                    "references": fk_map.get(column["name"]),
                }
            )

        with engine.connect() as connection:
            row_count = connection.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar_one()
        tables.append(
            {
                "name": table_name,
                "rowCount": row_count,
                "columns": columns,
            }
        )

    return tables


def _duckdb_table_summaries(settings: Settings | None = None) -> list[DatabaseTablePayload]:
    import duckdb

    duckdb_settings = get_database_settings(settings).duckdb
    connection = duckdb.connect(str(duckdb_settings.path), read_only=True)
    try:
        tables_rows = connection.execute(
            """
            SELECT table_name
            FROM duckdb_tables()
            WHERE database_name = ? AND schema_name = 'main'
            ORDER BY table_name
            """,
            [duckdb_settings.catalog_name],
        ).fetchall()

        columns_rows = connection.execute(
            """
            SELECT table_name, column_name, data_type, is_nullable, column_default, column_index
            FROM duckdb_columns()
            WHERE database_name = ? AND schema_name = 'main' AND internal = false
            ORDER BY table_name, column_index
            """,
            [duckdb_settings.catalog_name],
        ).fetchall()

        constraints_rows = connection.execute(
            """
            SELECT table_name, constraint_type, constraint_column_names, referenced_table, referenced_column_names
            FROM duckdb_constraints()
            WHERE database_name = ? AND schema_name = 'main'
            """,
            [duckdb_settings.catalog_name],
        ).fetchall()

        pk_columns: dict[str, set[str]] = {}
        fk_columns: dict[tuple[str, str], str] = {}
        for table_name, constraint_type, column_names, referenced_table, referenced_columns in constraints_rows:
            column_names = column_names or []
            if constraint_type == "PRIMARY KEY":
                pk_columns.setdefault(table_name, set()).update(column_names)
            if constraint_type == "FOREIGN KEY":
                referenced_columns = referenced_columns or []
                reference = f'{referenced_table}({", ".join(referenced_columns)})'
                for column_name in column_names:
                    fk_columns[(table_name, column_name)] = reference

        grouped_columns: dict[str, list[DatabaseColumnPayload]] = {}
        for table_name, column_name, data_type, is_nullable, column_default, _column_index in columns_rows:
            grouped_columns.setdefault(table_name, []).append(
                {
                    "name": column_name,
                    "type": data_type,
                    "nullable": str(is_nullable).lower() in {"true", "1", "yes"},
                    "defaultValue": column_default,
                    "isPrimaryKey": column_name in pk_columns.get(table_name, set()),
                    "references": fk_columns.get((table_name, column_name)),
                }
            )

        tables: list[DatabaseTablePayload] = []
        for (table_name,) in tables_rows:
            row = connection.execute(
                f'SELECT COUNT(*) AS count FROM "{table_name}"'
            ).fetchone()
            row_count = int(row[0]) if row is not None else 0
            tables.append(
                {
                    "name": table_name,
                    "rowCount": row_count,
                    "columns": grouped_columns.get(table_name, []),
                }
            )

        return tables
    finally:
        connection.close()


def _runtime_surface() -> DatabaseRuntimePayload:
    return {
        "analyticsReadBackend": "legacy",
        "conversationSummaryReadBackend": "legacy",
    }


def build_status_payload(
    *,
    status: DatabaseRefreshStatus,
    trigger: str,
    started_at: str,
    finished_at: str | None,
    duration_ms: int | None,
    error: str | None,
    last_successful_refresh_at: str | None,
    idempotency_key: str | None,
    scope_label: str,
    window_days: int,
    window_start: str | None,
    window_end: str | None,
    source_conversation_count: int,
    settings: Settings | None = None,
) -> DatabaseStatusPayload:
    database_settings = get_database_settings(settings)
    sqlite = database_settings.sqlite
    duckdb_settings = database_settings.duckdb
    sqlite_tables: list[DatabaseTablePayload] = []
    sqlite_error: str | None = None
    oltp_engine = create_oltp_engine(settings)
    try:
        sqlite_tables = _sqlite_table_summaries(oltp_engine)
    except Exception as exc:
        sqlite_error = str(exc)
    finally:
        oltp_engine.dispose()

    duckdb_tables: list[DatabaseTablePayload] = []
    duckdb_error: str | None = None
    if duckdb_settings.path.exists():
        try:
            duckdb_tables = _duckdb_table_summaries(settings)
        except Exception as exc:
            duckdb_error = str(exc)

    sqlite_size = _path_size(sqlite.path)
    duckdb_size = _path_size(duckdb_settings.path)

    return {
        "status": status,
        "trigger": trigger,
        "startedAt": started_at,
        "finishedAt": finished_at,
        "durationMs": duration_ms,
        "error": error,
        "lastSuccessfulRefreshAt": last_successful_refresh_at,
        "idempotencyKey": idempotency_key,
        "scopeLabel": scope_label,
        "windowDays": window_days,
        "windowStart": window_start,
        "windowEnd": window_end,
        "sourceConversationCount": source_conversation_count,
        "refreshIntervalMinutes": 360,
        "runtime": _runtime_surface(),
        "databases": {
            "frontendCache": {
                "key": "frontend_cache",
                "label": "Frontend Short-Term Cache",
                "engine": "In-process memory",
                "role": "cache",
                "availability": "ready",
                "health": "healthy",
                "operationalStatus": "Backend read cache available for conversation and analytics views.",
                "note": "Short-lived backend cache used to avoid redundant reads during active UI polling.",
                "error": None,
                "path": None,
                "target": "BackendServices.cache",
                "publicPath": None,
                "docsUrl": None,
                "tableCount": 0,
                "tables": [],
                "sizeBytes": None,
                "sizeDisplay": None,
                "inventorySummary": "Ephemeral in-memory cache",
                "load": [],
            },
            "sqlite": {
                "key": sqlite.key,
                "label": sqlite.label,
                "engine": sqlite.engine,
                "role": "metadata",
                "availability": "ready" if sqlite_error is None else "unreachable",
                "health": "healthy" if sqlite_error is None else "error",
                "operationalStatus": (
                    "Readable and serving historical conversations."
                    if sqlite_error is None
                    else "SQLite metadata store could not be inspected."
                ),
                "note": (
                    "App-local metadata, refresh bookkeeping, evaluations, and "
                    "historical detail tables."
                ),
                "error": sqlite_error,
                "path": str(sqlite.path),
                "target": None,
                "publicPath": sqlite.public_path,
                "docsUrl": sqlite.docs_url,
                "tableCount": len(sqlite_tables),
                "sizeBytes": sqlite_size,
                "sizeDisplay": _format_size(sqlite_size),
                "inventorySummary": f"{len(sqlite_tables)} table{'s' if len(sqlite_tables) != 1 else ''}",
                "load": [],
                "tables": sqlite_tables,
            },
            "duckdb": {
                "key": duckdb_settings.key,
                "label": duckdb_settings.label,
                "engine": duckdb_settings.engine,
                "role": "inspection",
                "availability": (
                    "ready"
                    if duckdb_settings.path.exists() and duckdb_error is None
                    else "unreachable"
                    if duckdb_settings.path.exists()
                    else "missing"
                ),
                "health": (
                    "healthy"
                    if duckdb_settings.path.exists() and duckdb_error is None
                    else "error"
                    if duckdb_settings.path.exists()
                    else "missing"
                ),
                "operationalStatus": (
                    "Inspection snapshot available for schema and table review."
                    if duckdb_settings.path.exists() and duckdb_error is None
                    else "DuckDB snapshot exists but could not be read."
                    if duckdb_settings.path.exists()
                    else "DuckDB inspection snapshot has not been generated."
                ),
                "note": (
                    "Optional DuckDB inspection snapshot. It is not on the "
                    "primary analytics serving path."
                ),
                "error": duckdb_error,
                "path": str(duckdb_settings.path),
                "target": None,
                "publicPath": duckdb_settings.public_path,
                "docsUrl": duckdb_settings.docs_url,
                "tableCount": len(duckdb_tables),
                "sizeBytes": duckdb_size,
                "sizeDisplay": _format_size(duckdb_size),
                "inventorySummary": f"{len(duckdb_tables)} table{'s' if len(duckdb_tables) != 1 else ''}",
                "load": [],
                "tables": duckdb_tables,
            },
            "prefectPostgres": {
                "key": "prefect_postgres",
                "label": "Prefect Postgres",
                "engine": "Postgres",
                "role": "orchestration",
                "availability": "ready",
                "health": "healthy",
                "operationalStatus": "Prefect control-plane database target configured for the local server stack.",
                "note": "Backing store for the self-hosted Prefect API and services stack.",
                "error": None,
                "path": None,
                "target": _prefect_postgres_target(),
                "publicPath": None,
                "docsUrl": None,
                "tableCount": 0,
                "tables": [],
                "sizeBytes": None,
                "sizeDisplay": None,
                "inventorySummary": "Catalog visibility is managed through Prefect/Postgres, not local file inspection.",
                "load": [],
            },
        },
    }


def load_status(settings: Settings | None = None) -> DatabaseStatusPayload | None:
    status_file = get_database_settings(settings).status_file
    if not status_file.exists():
        return None
    try:
        parsed = json.loads(status_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return parse_status_payload(parsed)


def write_status(payload: object, settings: Settings | None = None) -> None:
    validated = parse_status_payload(payload)
    if validated is None:
        raise ValueError("Invalid database status payload.")
    status_file = get_database_settings(settings).status_file
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(json.dumps(validated, ensure_ascii=True, indent=2), encoding="utf-8")


def parse_status_payload(payload: object) -> DatabaseStatusPayload | None:
    try:
        return _STATUS_PAYLOAD_ADAPTER.validate_python(_remap_legacy_database_aliases(payload))
    except ValidationError:
        return None


def _remap_legacy_database_aliases(payload: object) -> object:
    if not isinstance(payload, dict):
        return payload

    remapped = dict(payload)
    databases = remapped.get("databases")
    if not isinstance(databases, dict):
        return remapped

    normalized_databases = dict(databases)
    legacy_payload = normalized_databases.get("legacyDuckdb")
    if "duckdb" not in normalized_databases and isinstance(legacy_payload, dict):
        normalized_databases["duckdb"] = legacy_payload
    if "duckdb" not in normalized_databases and isinstance(normalized_databases.get("legacy_duckdb"), dict):
        normalized_databases["duckdb"] = normalized_databases["legacy_duckdb"]

    duckdb_payload = normalized_databases.get("duckdb")
    if isinstance(duckdb_payload, dict):
        artifact = dict(duckdb_payload)
        if artifact.get("key") == "legacy_duckdb":
            artifact["key"] = "duckdb"
        if artifact.get("role") == "legacy_debug":
            artifact["role"] = "inspection"
        normalized_databases["duckdb"] = artifact

    remapped["databases"] = normalized_databases
    return remapped


def main() -> None:
    status = load_status()
    print(json.dumps(status or {}, ensure_ascii=True))


if __name__ == "__main__":
    main()
