from __future__ import annotations

from helaicopter_api.server.config import DatabaseSettings, Settings, load_settings


def get_database_settings(settings: Settings | None = None) -> DatabaseSettings:
    backend_settings = settings or load_settings()
    return backend_settings.database


def ensure_runtime_dirs(settings: Settings | None = None) -> None:
    database_settings = get_database_settings(settings)
    for path in (
        database_settings.runtime_dir,
        database_settings.tools_dir,
        database_settings.sqlite.path.parent,
        database_settings.legacy_duckdb.path.parent,
        database_settings.sqlite.docs_dir,
        database_settings.legacy_duckdb.docs_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
