from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = REPO_ROOT / "var" / "database-runtime"
TOOLS_DIR = RUNTIME_DIR / "tools"
LOCK_FILE = RUNTIME_DIR / "refresh.lock"
STATUS_FILE = RUNTIME_DIR / "status.json"
PUBLIC_DIR = REPO_ROOT / "public"
DATABASE_ARTIFACTS_DIR = PUBLIC_DIR / "database-artifacts"
SCHEMA_DOCS_DIR = PUBLIC_DIR / "database-schemas"


@dataclass(frozen=True)
class DatabaseArtifact:
    key: str
    label: str
    engine: str
    path: Path
    docs_dir: Path
    public_path: str
    docs_url: str

    @property
    def sqlalchemy_url(self) -> str:
        if self.key == "oltp":
            return f"sqlite:///{self.path}"
        return f"duckdb:///{self.path}"

    @property
    def catalog_name(self) -> str:
        return self.path.stem


OLTP_ARTIFACT = DatabaseArtifact(
    key="oltp",
    label="OLTP",
    engine="SQLite",
    path=DATABASE_ARTIFACTS_DIR / "oltp" / "helaicopter_oltp.sqlite",
    docs_dir=SCHEMA_DOCS_DIR / "oltp",
    public_path="/database-artifacts/oltp/helaicopter_oltp.sqlite",
    docs_url="/database-schemas/oltp/index.html",
)

OLAP_ARTIFACT = DatabaseArtifact(
    key="olap",
    label="OLAP",
    engine="DuckDB",
    path=DATABASE_ARTIFACTS_DIR / "olap" / "helaicopter_olap.duckdb",
    docs_dir=SCHEMA_DOCS_DIR / "olap",
    public_path="/database-artifacts/olap/helaicopter_olap.duckdb",
    docs_url="/database-schemas/olap/index.html",
)

ARTIFACTS = {
    OLTP_ARTIFACT.key: OLTP_ARTIFACT,
    OLAP_ARTIFACT.key: OLAP_ARTIFACT,
}


def ensure_runtime_dirs() -> None:
    for path in (
        RUNTIME_DIR,
        TOOLS_DIR,
        OLTP_ARTIFACT.path.parent,
        OLAP_ARTIFACT.path.parent,
        OLTP_ARTIFACT.docs_dir,
        OLAP_ARTIFACT.docs_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
