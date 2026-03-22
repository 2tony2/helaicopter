"""Concrete OpenCloud adapter backed by the local OpenCode SQLite database."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from urllib.parse import quote

from helaicopter_api.ports.opencloud_sqlite import (
    OpenCloudMessageRecord,
    OpenCloudPartRecord,
    OpenCloudSessionRecord,
    OpenCloudStore,
)


class FileOpenCloudStore(OpenCloudStore):
    """Read OpenCloud/OpenCode sessions from ``opencode.db`` in readonly mode."""

    def __init__(self, *, db_path: Path) -> None:
        self._db_path = db_path

    def list_sessions(self) -> list[OpenCloudSessionRecord]:
        connection = self._connect_readonly()
        if connection is None:
            return []
        try:
            if not _table_exists(connection, "session"):
                return []
            rows = connection.execute(
                """
                SELECT
                  id,
                  project_id,
                  parent_id,
                  slug,
                  directory,
                  title,
                  version,
                  time_created,
                  time_updated
                FROM session
                ORDER BY time_updated DESC, id ASC
                """
            ).fetchall()
            return [_map_session_row(row) for row in rows]
        finally:
            connection.close()

    def get_session(self, session_id: str) -> OpenCloudSessionRecord | None:
        connection = self._connect_readonly()
        if connection is None:
            return None
        try:
            if not _table_exists(connection, "session"):
                return None
            row = connection.execute(
                """
                SELECT
                  id,
                  project_id,
                  parent_id,
                  slug,
                  directory,
                  title,
                  version,
                  time_created,
                  time_updated
                FROM session
                WHERE id = ?
                """,
                (session_id,),
            ).fetchone()
            return _map_session_row(row) if row is not None else None
        finally:
            connection.close()

    def list_messages(self, session_id: str) -> list[OpenCloudMessageRecord]:
        connection = self._connect_readonly()
        if connection is None:
            return []
        try:
            if not _table_exists(connection, "message"):
                return []
            rows = connection.execute(
                """
                SELECT id, session_id, time_created, time_updated, data
                FROM message
                WHERE session_id = ?
                ORDER BY time_created ASC, id ASC
                """,
                (session_id,),
            ).fetchall()
            return [_map_message_row(row) for row in rows]
        finally:
            connection.close()

    def list_parts(self, session_id: str) -> list[OpenCloudPartRecord]:
        connection = self._connect_readonly()
        if connection is None:
            return []
        try:
            if not _table_exists(connection, "part"):
                return []
            rows = connection.execute(
                """
                SELECT id, message_id, session_id, time_created, time_updated, data
                FROM part
                WHERE session_id = ?
                ORDER BY time_created ASC, id ASC
                """,
                (session_id,),
            ).fetchall()
            return [_map_part_row(row) for row in rows]
        finally:
            connection.close()

    def _connect_readonly(self) -> sqlite3.Connection | None:
        if not self._db_path.exists():
            return None
        uri = f"file:{quote(str(self._db_path))}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        return connection


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _json_dict(raw: object) -> dict[str, object]:
    if not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _map_session_row(row: sqlite3.Row) -> OpenCloudSessionRecord:
    return OpenCloudSessionRecord(
        id=row["id"],
        project_id=row["project_id"],
        parent_id=row["parent_id"],
        slug=row["slug"],
        directory=row["directory"],
        title=row["title"],
        version=row["version"],
        time_created=row["time_created"],
        time_updated=row["time_updated"],
    )


def _map_message_row(row: sqlite3.Row) -> OpenCloudMessageRecord:
    return OpenCloudMessageRecord(
        id=row["id"],
        session_id=row["session_id"],
        time_created=row["time_created"],
        time_updated=row["time_updated"],
        data=_json_dict(row["data"]),
    )


def _map_part_row(row: sqlite3.Row) -> OpenCloudPartRecord:
    return OpenCloudPartRecord(
        id=row["id"],
        message_id=row["message_id"],
        session_id=row["session_id"],
        time_created=row["time_created"],
        time_updated=row["time_updated"],
        data=_json_dict(row["data"]),
    )
