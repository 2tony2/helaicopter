from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = REPO_ROOT / "var" / "database-runtime"
TOOLS_DIR = RUNTIME_DIR / "tools"
LOCK_FILE = RUNTIME_DIR / "refresh.lock"
STATUS_FILE = RUNTIME_DIR / "status.json"
PUBLIC_DIR = REPO_ROOT / "public"
DATABASE_ARTIFACTS_DIR = PUBLIC_DIR / "database-artifacts"
SCHEMA_DOCS_DIR = PUBLIC_DIR / "database-schemas"


def _read_bool_env(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _read_int_env(name: str, *, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    return int(raw)


@dataclass(frozen=True)
class DatabaseArtifact:
    key: str
    label: str
    engine: str
    sqlalchemy_driver: str
    path: Path
    docs_dir: Path
    public_path: str
    docs_url: str

    @property
    def sqlalchemy_url(self) -> str:
        return f"{self.sqlalchemy_driver}:///{self.path}"

    @property
    def catalog_name(self) -> str:
        return self.path.stem


SQLITE_ARTIFACT = DatabaseArtifact(
    key="sqlite",
    label="SQLite Metadata Store",
    engine="SQLite",
    sqlalchemy_driver="sqlite",
    path=DATABASE_ARTIFACTS_DIR / "oltp" / "helaicopter_oltp.sqlite",
    docs_dir=SCHEMA_DOCS_DIR / "oltp",
    public_path="/database-artifacts/oltp/helaicopter_oltp.sqlite",
    docs_url="/database-schemas/oltp/index.html",
)

DUCKDB_LEGACY_ARTIFACT = DatabaseArtifact(
    key="legacy_duckdb",
    label="Legacy DuckDB Snapshot",
    engine="DuckDB",
    sqlalchemy_driver="duckdb",
    path=DATABASE_ARTIFACTS_DIR / "olap" / "helaicopter_olap.duckdb",
    docs_dir=SCHEMA_DOCS_DIR / "olap",
    public_path="/database-artifacts/olap/helaicopter_olap.duckdb",
    docs_url="/database-schemas/olap/index.html",
)

# Legacy aliases kept while the refresh/migration tooling still uses the old
# names internally. User-facing status surfaces should prefer the new names.
OLTP_ARTIFACT = SQLITE_ARTIFACT
OLAP_ARTIFACT = DUCKDB_LEGACY_ARTIFACT

ARTIFACTS = {
    SQLITE_ARTIFACT.key: SQLITE_ARTIFACT,
    DUCKDB_LEGACY_ARTIFACT.key: DUCKDB_LEGACY_ARTIFACT,
}


def ensure_runtime_dirs() -> None:
    for path in (
        RUNTIME_DIR,
        TOOLS_DIR,
        SQLITE_ARTIFACT.path.parent,
        DUCKDB_LEGACY_ARTIFACT.path.parent,
        SQLITE_ARTIFACT.docs_dir,
        DUCKDB_LEGACY_ARTIFACT.docs_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
