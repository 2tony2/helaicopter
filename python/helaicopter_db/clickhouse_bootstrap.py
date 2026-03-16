from __future__ import annotations

import argparse
import base64
import ssl
from dataclasses import replace
from pathlib import Path
import time
from typing import Iterable
from urllib import error, request

from .settings import CLICKHOUSE_DDL_DIR, CLICKHOUSE_SETTINGS, ClickHouseConnectionSettings


def _build_client(settings: ClickHouseConnectionSettings) -> tuple[str, dict[str, str]]:
    auth = f"{settings.user}:{settings.password}".encode("utf-8")
    headers = {
        "Authorization": f"Basic {base64.b64encode(auth).decode('ascii')}",
        "Content-Type": "text/plain; charset=utf-8",
    }
    return settings.base_url, headers


def _post_sql(
    settings: ClickHouseConnectionSettings,
    sql: str,
    *,
    database: str = "default",
) -> None:
    base_url, headers = _build_client(settings)
    url = (
        f"{base_url}/?database={database}"
        "&wait_end_of_query=1"
        "&output_format_json_quote_64bit_integers=0"
    )
    payload = sql.encode("utf-8")
    req = request.Request(url, data=payload, headers=headers, method="POST")
    timeout = max(settings.connect_timeout_seconds, settings.send_receive_timeout_seconds)
    ssl_context = None
    if settings.secure and not settings.verify_tls:
        ssl_context = ssl._create_unverified_context()
    try:
        with request.urlopen(req, timeout=timeout, context=ssl_context) as response:
            response.read()
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(body or str(exc)) from exc
    except error.URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc
    except OSError as exc:
        raise RuntimeError(str(exc)) from exc


def _wait_for_ready(
    settings: ClickHouseConnectionSettings,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float = 1.0,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: RuntimeError | None = None
    while time.monotonic() < deadline:
        try:
            _post_sql(settings, "SELECT 1 FORMAT Null")
            return
        except RuntimeError as exc:
            last_error = exc
            time.sleep(poll_interval_seconds)

    raise RuntimeError(
        "Timed out waiting for ClickHouse to become ready"
        + (f": {last_error}" if last_error else "")
    )


def _render_sql(sql: str, settings: ClickHouseConnectionSettings) -> str:
    return sql.replace("{{database}}", settings.database)


def _iter_sql_files(ddl_dir: Path) -> Iterable[Path]:
    return sorted(path for path in ddl_dir.glob("*.sql") if path.is_file())


def apply_clickhouse_schema(
    settings: ClickHouseConnectionSettings,
    *,
    ddl_dir: Path = CLICKHOUSE_DDL_DIR,
    wait_for_ready: bool = False,
    wait_timeout_seconds: float = 30.0,
) -> list[Path]:
    if not ddl_dir.exists():
        raise FileNotFoundError(f"DDL directory does not exist: {ddl_dir}")

    sql_files = list(_iter_sql_files(ddl_dir))
    if not sql_files:
        raise FileNotFoundError(f"No ClickHouse DDL files found in {ddl_dir}")

    if wait_for_ready:
        _wait_for_ready(settings, timeout_seconds=wait_timeout_seconds)

    for sql_file in sql_files:
        statement = _render_sql(sql_file.read_text(encoding="utf-8"), settings).strip()
        if not statement:
            continue
        _post_sql(settings, statement)

    return sql_files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize the tracked ClickHouse schema for local development.",
    )
    parser.add_argument("--ddl-dir", type=Path, default=CLICKHOUSE_DDL_DIR)
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--database")
    parser.add_argument("--user")
    parser.add_argument("--password")
    parser.add_argument("--secure", action="store_true")
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--wait-for-ready", action="store_true")
    parser.add_argument("--wait-timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    overrides = {
        "host": args.host or CLICKHOUSE_SETTINGS.host,
        "port": args.port or CLICKHOUSE_SETTINGS.port,
        "database": args.database or CLICKHOUSE_SETTINGS.database,
        "user": args.user or CLICKHOUSE_SETTINGS.user,
        "password": args.password if args.password is not None else CLICKHOUSE_SETTINGS.password,
        "secure": args.secure or CLICKHOUSE_SETTINGS.secure,
        "verify_tls": False if args.insecure else CLICKHOUSE_SETTINGS.verify_tls,
    }
    settings = replace(CLICKHOUSE_SETTINGS, **overrides)
    applied_files = apply_clickhouse_schema(
        settings,
        ddl_dir=args.ddl_dir,
        wait_for_ready=args.wait_for_ready,
        wait_timeout_seconds=args.wait_timeout_seconds,
    )

    print(f"Applied {len(applied_files)} ClickHouse DDL files to {settings.redacted_url}")
    for path in applied_files:
        print(f" - {path.name}")


if __name__ == "__main__":
    main()
