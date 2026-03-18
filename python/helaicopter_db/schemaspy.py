from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from urllib.request import urlretrieve

from helaicopter_api.server.config import DatabaseArtifactSettings, Settings

from .settings import get_database_settings


SCHEMASPY_VERSION = "6.2.4"
DUCKDB_JDBC_VERSION = "1.4.4.0"
SQLITE_JDBC_VERSION = "3.50.3.0"


def ensure_schemaspy_tools(settings: Settings | None = None) -> dict[str, Path]:
    tools_dir = get_database_settings(settings).tools_dir
    tools_dir.mkdir(parents=True, exist_ok=True)

    schemaspy_jar = tools_dir / f"schemaspy-{SCHEMASPY_VERSION}.jar"
    duckdb_jar = tools_dir / f"duckdb_jdbc-{DUCKDB_JDBC_VERSION}.jar"
    sqlite_jar = tools_dir / f"sqlite-jdbc-{SQLITE_JDBC_VERSION}.jar"
    duckdb_profile = tools_dir / "duckdb.properties"

    downloads = {
        schemaspy_jar: f"https://github.com/schemaspy/schemaspy/releases/download/v{SCHEMASPY_VERSION}/schemaspy-{SCHEMASPY_VERSION}.jar",
        duckdb_jar: f"https://repo1.maven.org/maven2/org/duckdb/duckdb_jdbc/{DUCKDB_JDBC_VERSION}/duckdb_jdbc-{DUCKDB_JDBC_VERSION}.jar",
        sqlite_jar: f"https://repo1.maven.org/maven2/org/xerial/sqlite-jdbc/{SQLITE_JDBC_VERSION}/sqlite-jdbc-{SQLITE_JDBC_VERSION}.jar",
    }

    for target, url in downloads.items():
        if not target.exists():
            urlretrieve(url, target)

    duckdb_profile.write_text(
        "\n".join(
            [
                "dbms=DuckDB",
                "description=DuckDB",
                "extends=pgsql11",
                "connectionSpec=jdbc:duckdb:<db>",
                "db=absolute path to database",
                "driver=org.duckdb.DuckDBDriver",
                "selectSchemasSql=SELECT schema_name, NULL AS schema_comment FROM information_schema.schemata WHERE catalog_name = :catalog AND schema_name = :schema",
                "selectCatalogsSql=SELECT database_name AS catalog_name, comment AS catalog_comment FROM duckdb_databases() WHERE database_name = :catalog",
                "selectTablesSql=SELECT table_name, database_name AS table_catalog, schema_name AS table_schema, comment AS table_comment, estimated_size AS table_rows FROM duckdb_tables() WHERE database_name = :catalog AND schema_name = :schema",
                "selectViewSql=select sql as view_definition from duckdb_views() where database_name = :catalog and schema_name = :schema and view_name = :table",
                "selectRoutinesSql=SELECT NULL AS routine_name, NULL AS routine_type, NULL AS dtd_identifier, NULL AS routine_body, NULL AS routine_definition, NULL AS sql_data_access, NULL AS security_type, NULL AS is_deterministic, NULL AS routine_comment LIMIT 0",
                "selectRoutineParametersSql=SELECT NULL AS specific_name, NULL AS parameter_name, NULL AS parameter_mode, NULL AS dtd_identifier LIMIT 0",
                "selectCheckConstraintsSql=select table_name, constraint_name, expression as text from duckdb_constraints() where database_name = :catalog and constraint_type = 'CHECK' and schema_name = :schema",
                "selectSequencesSql=SELECT sequence_name, start_value, increment_by AS increment FROM duckdb_sequences() WHERE database_name = :catalog AND schema_name = :schema",
                "selectRowCountSql=SELECT estimated_size AS row_count from duckdb_tables() WHERE database_name = :catalog AND schema_name = :schema AND table_name = :table",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "schemaspy_jar": schemaspy_jar,
        "duckdb_jar": duckdb_jar,
        "sqlite_jar": sqlite_jar,
        "duckdb_profile": duckdb_profile,
    }


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True, text=True)


def _sanitize_schema_docs(artifact: DatabaseArtifactSettings) -> None:
    absolute_db_path = str(artifact.path)
    absolute_xml_path = f"{absolute_db_path}.main.xml"
    replacements = (
        (absolute_xml_path, f"./{artifact.path.name}.main.xml"),
        (absolute_db_path, artifact.public_path),
    )

    for file_path in artifact.docs_dir.rglob("*"):
        if not file_path.is_file():
            continue

        try:
            contents = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        updated = contents
        for original, replacement in replacements:
            updated = updated.replace(original, replacement)

        if updated != contents:
            file_path.write_text(updated, encoding="utf-8")


def generate_schema_docs(settings: Settings | None = None) -> None:
    tools = ensure_schemaspy_tools(settings)
    database_settings = get_database_settings(settings)
    sqlite = database_settings.sqlite
    legacy_duckdb = database_settings.legacy_duckdb

    for docs_dir in (sqlite.docs_dir, legacy_duckdb.docs_dir):
        if docs_dir.exists():
            shutil.rmtree(docs_dir)
        docs_dir.mkdir(parents=True, exist_ok=True)

    _run(
        [
            "java",
            "-jar",
            str(tools["schemaspy_jar"]),
            "-t",
            "sqlite-xerial",
            "-dp",
            str(tools["sqlite_jar"]),
            "-db",
            str(sqlite.path),
            "-s",
            "main",
            "-cat",
            "%",
            "-u",
            "schemaspy",
            "-o",
            str(sqlite.docs_dir),
            "-vizjs",
        ]
    )
    _sanitize_schema_docs(sqlite)

    _run(
        [
            "java",
            "-jar",
            str(tools["schemaspy_jar"]),
            "-t",
            str(tools["duckdb_profile"]),
            "-dp",
            str(tools["duckdb_jar"]),
            "-db",
            str(legacy_duckdb.path),
            "-s",
            "main",
            "-cat",
            legacy_duckdb.catalog_name,
            "-u",
            "schemaspy",
            "-o",
            str(legacy_duckdb.docs_dir),
            "-vizjs",
        ]
    )
    _sanitize_schema_docs(legacy_duckdb)
