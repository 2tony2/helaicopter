#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import signal
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import Mapping, Sequence

APP_NAME = "helaicopter"
DISPLAY_NAME = "Helaicopter"
EXCLUDED_SOURCE_NAMES = {
    ".git",
    ".next",
    ".venv",
    ".worktrees",
    "__pycache__",
    "node_modules",
}


def default_runtime_root(env: Mapping[str, str]) -> Path:
    explicit_home = env.get("HELAICOPTER_HOME")
    if explicit_home:
        return Path(explicit_home).expanduser()

    xdg_data_home = env.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home).expanduser() / APP_NAME

    home = Path(env.get("HOME", str(Path.home()))).expanduser()
    if platform.system() == "Darwin":
        return home / "Library" / "Application Support" / DISPLAY_NAME

    return home / ".local" / "share" / APP_NAME


def load_staged_version(staged_root: Path) -> str:
    package_json = staged_root / "package.json"
    payload = json.loads(package_json.read_text(encoding="utf-8"))
    return str(payload["version"])


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    ignored = set(EXCLUDED_SOURCE_NAMES)
    ignored.update(name for name in names if name.endswith((".pyc", ".pyo")))
    return ignored


def sync_staged_source(staged_root: Path, runtime_root: Path) -> Path:
    runtime_root.mkdir(parents=True, exist_ok=True)
    runtime_app = runtime_root / "app"
    if runtime_app.exists():
        shutil.rmtree(runtime_app)
    shutil.copytree(staged_root, runtime_app, ignore=_copy_ignore)
    (runtime_root / ".staged-version").write_text(load_staged_version(staged_root), encoding="utf-8")
    return runtime_app


def bootstrap_commands(_app_root: Path) -> list[list[str]]:
    return [
        ["npm", "install", "--omit=dev", "--no-fund", "--no-audit"],
        ["uv", "sync", "--frozen"],
        ["npm", "run", "build"],
    ]


def run_bootstrap(app_root: Path, env: Mapping[str, str]) -> None:
    for command in bootstrap_commands(app_root):
        subprocess.run(command, cwd=app_root, check=True, env=dict(env))


def ensure_runtime(staged_root: Path, runtime_root: Path, env: Mapping[str, str]) -> Path:
    app_root = sync_staged_source(staged_root, runtime_root)
    run_bootstrap(app_root, env)
    return app_root


def backend_command(api_port: int) -> list[str]:
    return [
        "uv",
        "run",
        "uvicorn",
        "helaicopter_api.server.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(api_port),
    ]


def frontend_command(port: int) -> list[str]:
    return [
        "npm",
        "run",
        "start",
        "--",
        "--hostname",
        "127.0.0.1",
        "--port",
        str(port),
    ]


def terminate_processes(processes: Sequence[subprocess.Popen[bytes] | subprocess.Popen[str]]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()

    deadline = time.time() + 5
    for process in processes:
        if process.poll() is not None:
            continue
        timeout = max(0.0, deadline - time.time())
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()


def serve(
    staged_root: Path,
    runtime_root: Path,
    env: Mapping[str, str],
    *,
    port: int,
    api_port: int,
    open_browser: bool,
) -> int:
    app_root = ensure_runtime(staged_root, runtime_root, env)
    backend = subprocess.Popen(backend_command(api_port), cwd=app_root, env=dict(env))
    frontend_env = dict(env)
    frontend_env["NEXT_PUBLIC_API_BASE_URL"] = f"http://127.0.0.1:{api_port}"
    frontend = subprocess.Popen(frontend_command(port), cwd=app_root, env=frontend_env)
    processes = [backend, frontend]

    def handle_shutdown(signum: int, _frame: object) -> None:
        terminate_processes(processes)
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    if open_browser:
        webbrowser.open(f"http://127.0.0.1:{port}", new=2)

    while True:
        backend_code = backend.poll()
        frontend_code = frontend.poll()
        if backend_code is None and frontend_code is None:
            time.sleep(0.5)
            continue

        terminate_processes(processes)
        return backend_code if backend_code is not None else frontend_code or 0


def resolve_staged_root(env: Mapping[str, str], cli_value: str | None) -> Path:
    raw_path = cli_value or env.get("HELAICOPTER_STAGED_ROOT")
    if not raw_path:
        raise SystemExit("HELAICOPTER_STAGED_ROOT is not set. Reinstall via Homebrew or set it manually.")
    return Path(raw_path).expanduser().resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=APP_NAME)
    parser.add_argument("--runtime-root", help="Override the writable runtime directory")
    parser.add_argument("--staged-root", help="Override the staged source directory from Homebrew")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("bootstrap", help="Refresh the writable runtime and install runtime dependencies")

    paths_parser = subparsers.add_parser("paths", help="Print the staged and runtime paths as JSON")
    paths_parser.add_argument("--pretty", action="store_true")

    serve_parser = subparsers.add_parser("serve", help="Bootstrap and run the backend and frontend")
    serve_parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "3000")))
    serve_parser.add_argument("--api-port", type=int, default=int(os.environ.get("HELA_API_PORT", "30000")))
    serve_parser.add_argument("--open", action="store_true", help="Open the app in the default browser")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    env = dict(os.environ)
    runtime_root = Path(args.runtime_root).expanduser() if args.runtime_root else default_runtime_root(env)
    staged_root = resolve_staged_root(env, args.staged_root)

    if args.command == "bootstrap":
        ensure_runtime(staged_root, runtime_root, env)
        return 0

    if args.command == "paths":
        payload = {
            "staged_root": str(staged_root),
            "runtime_root": str(runtime_root),
            "display_name": DISPLAY_NAME,
        }
        print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
        return 0

    if args.command == "serve":
        return serve(
            staged_root,
            runtime_root,
            env,
            port=args.port,
            api_port=args.api_port,
            open_browser=args.open,
        )

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
