from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Final


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = REPO_ROOT / "var" / "database-runtime"
TOOLS_DIR = RUNTIME_DIR / "tools"
LOCK_FILE = RUNTIME_DIR / "refresh.lock"
STATUS_FILE = RUNTIME_DIR / "status.json"
PUBLIC_DIR = REPO_ROOT / "public"
DATABASE_ARTIFACTS_DIR = PUBLIC_DIR / "database-artifacts"
SCHEMA_DOCS_DIR = PUBLIC_DIR / "database-schemas"
CLICKHOUSE_DDL_DIR = REPO_ROOT / "sql" / "clickhouse"
CLICKHOUSE_LOCAL_DIR = REPO_ROOT / "var" / "clickhouse-local"
CLICKHOUSE_LOCAL_DATA_DIR = CLICKHOUSE_LOCAL_DIR / "data"
CLICKHOUSE_LOCAL_LOG_DIR = CLICKHOUSE_LOCAL_DIR / "log"

_CLICKHOUSE_IDENTIFIER_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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


def _read_float_env(name: str, *, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


def _validate_clickhouse_identifier(value: str) -> str:
    if not _CLICKHOUSE_IDENTIFIER_RE.fullmatch(value):
        raise ValueError(
            "ClickHouse identifiers must match [A-Za-z_][A-Za-z0-9_]*: "
            f"received {value!r}"
        )
    return value


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


@dataclass(frozen=True)
class ClickHouseConnectionSettings:
    host: str
    port: int
    native_port: int
    database: str
    user: str
    password: str
    secure: bool
    verify_tls: bool
    connect_timeout_seconds: float
    send_receive_timeout_seconds: float
    local_data_dir: Path
    local_log_dir: Path

    @property
    def scheme(self) -> str:
        return "https" if self.secure else "http"

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    @property
    def redacted_url(self) -> str:
        return f"{self.scheme}://{self.user}@{self.host}:{self.port}/{self.database}"


def load_clickhouse_settings() -> ClickHouseConnectionSettings:
    return ClickHouseConnectionSettings(
        host=os.getenv("HELAICOPTER_CLICKHOUSE_HOST", "127.0.0.1"),
        port=_read_int_env("HELAICOPTER_CLICKHOUSE_PORT", default=8123),
        native_port=_read_int_env("HELAICOPTER_CLICKHOUSE_NATIVE_PORT", default=9000),
        database=_validate_clickhouse_identifier(
            os.getenv("HELAICOPTER_CLICKHOUSE_DATABASE", "helaicopter")
        ),
        user=os.getenv("HELAICOPTER_CLICKHOUSE_USER", "helaicopter"),
        password=os.getenv("HELAICOPTER_CLICKHOUSE_PASSWORD", "helaicopter"),
        secure=_read_bool_env("HELAICOPTER_CLICKHOUSE_SECURE", default=False),
        verify_tls=_read_bool_env("HELAICOPTER_CLICKHOUSE_VERIFY_TLS", default=True),
        connect_timeout_seconds=_read_float_env(
            "HELAICOPTER_CLICKHOUSE_CONNECT_TIMEOUT_SECONDS",
            default=5.0,
        ),
        send_receive_timeout_seconds=_read_float_env(
            "HELAICOPTER_CLICKHOUSE_SEND_RECEIVE_TIMEOUT_SECONDS",
            default=30.0,
        ),
        local_data_dir=CLICKHOUSE_LOCAL_DATA_DIR,
        local_log_dir=CLICKHOUSE_LOCAL_LOG_DIR,
    )


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
CLICKHOUSE_SETTINGS = load_clickhouse_settings()
CLICKHOUSE_BACKFILL_ENABLED = _read_bool_env(
    "HELAICOPTER_ENABLE_CLICKHOUSE_BACKFILL",
    default=False,
)


def ensure_runtime_dirs() -> None:
    for path in (
        RUNTIME_DIR,
        TOOLS_DIR,
        OLTP_ARTIFACT.path.parent,
        OLAP_ARTIFACT.path.parent,
        OLTP_ARTIFACT.docs_dir,
        OLAP_ARTIFACT.docs_dir,
        CLICKHOUSE_LOCAL_DATA_DIR,
        CLICKHOUSE_LOCAL_LOG_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
