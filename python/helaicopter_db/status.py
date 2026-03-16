from __future__ import annotations

import json
from typing import Any

from sqlalchemy import inspect, text

from .db import create_oltp_engine
from .settings import (
    DUCKDB_LEGACY_ARTIFACT,
    SQLITE_ARTIFACT,
    STATUS_FILE,
)


def _sqlite_table_summaries(engine) -> list[dict[str, Any]]:
    inspector = inspect(engine)
    tables = []

    for table_name in sorted(inspector.get_table_names()):
        pk_columns = set(inspector.get_pk_constraint(table_name).get("constrained_columns", []))
        fk_map: dict[str, str] = {}
        for foreign_key in inspector.get_foreign_keys(table_name):
            referred_table = foreign_key.get("referred_table")
            referred_columns = foreign_key.get("referred_columns") or []
            for column_name in foreign_key.get("constrained_columns") or []:
                fk_map[column_name] = f"{referred_table}({', '.join(referred_columns)})"

        columns = []
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


def _legacy_duckdb_table_summaries() -> list[dict[str, Any]]:
    import duckdb

    connection = duckdb.connect(str(DUCKDB_LEGACY_ARTIFACT.path), read_only=True)
    try:
        tables_rows = connection.execute(
            """
            SELECT table_name
            FROM duckdb_tables()
            WHERE database_name = ? AND schema_name = 'main'
            ORDER BY table_name
            """,
            [DUCKDB_LEGACY_ARTIFACT.catalog_name],
        ).fetchall()

        columns_rows = connection.execute(
            """
            SELECT table_name, column_name, data_type, is_nullable, column_default, column_index
            FROM duckdb_columns()
            WHERE database_name = ? AND schema_name = 'main' AND internal = false
            ORDER BY table_name, column_index
            """,
            [DUCKDB_LEGACY_ARTIFACT.catalog_name],
        ).fetchall()

        constraints_rows = connection.execute(
            """
            SELECT table_name, constraint_type, constraint_column_names, referenced_table, referenced_column_names
            FROM duckdb_constraints()
            WHERE database_name = ? AND schema_name = 'main'
            """,
            [DUCKDB_LEGACY_ARTIFACT.catalog_name],
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

        grouped_columns: dict[str, list[dict[str, Any]]] = {}
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

        tables = []
        for (table_name,) in tables_rows:
            row_count = connection.execute(
                f'SELECT COUNT(*) AS count FROM "{table_name}"'
            ).fetchone()[0]
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


def _runtime_surface() -> dict[str, Any]:
    return {
        "analyticsReadBackend": "legacy",
        "conversationSummaryReadBackend": "legacy",
    }


def build_status_payload(
    *,
    status: str,
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
) -> dict[str, Any]:
    sqlite_tables: list[dict[str, Any]] = []
    sqlite_error: str | None = None
    oltp_engine = create_oltp_engine()
    try:
        sqlite_tables = _sqlite_table_summaries(oltp_engine)
    except Exception as exc:
        sqlite_error = str(exc)
    finally:
        oltp_engine.dispose()

    legacy_duckdb_tables: list[dict[str, Any]] = []
    legacy_duckdb_error: str | None = None
    if DUCKDB_LEGACY_ARTIFACT.path.exists():
        try:
            legacy_duckdb_tables = _legacy_duckdb_table_summaries()
        except Exception as exc:
            legacy_duckdb_error = str(exc)

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
            "sqlite": {
                "key": SQLITE_ARTIFACT.key,
                "label": SQLITE_ARTIFACT.label,
                "engine": SQLITE_ARTIFACT.engine,
                "role": "metadata",
                "availability": "ready" if sqlite_error is None else "unreachable",
                "note": (
                    "App-local metadata, refresh bookkeeping, evaluations, and "
                    "historical detail tables."
                ),
                "error": sqlite_error,
                "path": str(SQLITE_ARTIFACT.path),
                "target": None,
                "publicPath": SQLITE_ARTIFACT.public_path,
                "docsUrl": SQLITE_ARTIFACT.docs_url,
                "tableCount": len(sqlite_tables),
                "tables": sqlite_tables,
            },
            "legacyDuckdb": {
                "key": DUCKDB_LEGACY_ARTIFACT.key,
                "label": DUCKDB_LEGACY_ARTIFACT.label,
                "engine": DUCKDB_LEGACY_ARTIFACT.engine,
                "role": "legacy_debug",
                "availability": (
                    "ready"
                    if DUCKDB_LEGACY_ARTIFACT.path.exists() and legacy_duckdb_error is None
                    else "unreachable"
                    if DUCKDB_LEGACY_ARTIFACT.path.exists()
                    else "missing"
                ),
                "note": (
                    "Legacy compatibility/debug artifact only. It is not on the "
                    "primary analytics serving path."
                ),
                "error": legacy_duckdb_error,
                "path": str(DUCKDB_LEGACY_ARTIFACT.path),
                "target": None,
                "publicPath": DUCKDB_LEGACY_ARTIFACT.public_path,
                "docsUrl": DUCKDB_LEGACY_ARTIFACT.docs_url,
                "tableCount": len(legacy_duckdb_tables),
                "tables": legacy_duckdb_tables,
            },
        },
    }


def load_status() -> dict[str, Any] | None:
    if not STATUS_FILE.exists():
        return None
    return json.loads(STATUS_FILE.read_text(encoding="utf-8"))


def write_status(payload: dict[str, Any]) -> None:
    STATUS_FILE.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def main() -> None:
    status = load_status()
    print(json.dumps(status or {}, ensure_ascii=True))


if __name__ == "__main__":
    main()
