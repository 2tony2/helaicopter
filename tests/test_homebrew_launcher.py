from __future__ import annotations

import importlib.util
from pathlib import Path


def load_launcher():
    launcher_path = Path(__file__).resolve().parents[1] / "packaging/homebrew" / "launcher.py"
    spec = importlib.util.spec_from_file_location("homebrew_launcher", launcher_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_runtime_root_prefers_explicit_home(tmp_path: Path) -> None:
    launcher = load_launcher()

    runtime_root = launcher.default_runtime_root(
        {
            "HELAICOPTER_HOME": str(tmp_path / "custom-home"),
            "HOME": str(tmp_path),
        }
    )

    assert runtime_root == tmp_path / "custom-home"


def test_sync_staged_source_copies_project_files_without_mutable_artifacts(tmp_path: Path) -> None:
    launcher = load_launcher()
    staged_root = tmp_path / "staged"
    runtime_root = tmp_path / "runtime"
    staged_root.mkdir()
    (staged_root / "package.json").write_text('{"version":"0.1.0"}', encoding="utf-8")
    (staged_root / "README.md").write_text("# Helaicopter", encoding="utf-8")
    (staged_root / "node_modules").mkdir()
    (staged_root / "node_modules" / "ignore-me.js").write_text("ignored", encoding="utf-8")
    (staged_root / ".venv").mkdir()
    (staged_root / ".venv" / "pyvenv.cfg").write_text("ignored", encoding="utf-8")
    (staged_root / ".next").mkdir()
    (staged_root / ".next" / "build-manifest.json").write_text("ignored", encoding="utf-8")
    runtime_app = runtime_root / "app"
    runtime_app.mkdir(parents=True)
    (runtime_app / "stale.txt").write_text("remove-me", encoding="utf-8")

    synced_app = launcher.sync_staged_source(staged_root, runtime_root)

    assert synced_app == runtime_app
    assert (runtime_app / "README.md").read_text(encoding="utf-8") == "# Helaicopter"
    assert not (runtime_app / "node_modules").exists()
    assert not (runtime_app / ".venv").exists()
    assert not (runtime_app / ".next").exists()
    assert not (runtime_app / "stale.txt").exists()
    assert (runtime_root / ".staged-version").read_text(encoding="utf-8").strip() == "0.1.0"


def test_bootstrap_commands_use_production_installs(tmp_path: Path) -> None:
    launcher = load_launcher()

    commands = launcher.bootstrap_commands(tmp_path / "runtime" / "app")

    assert commands == [
        ["npm", "install", "--omit=dev", "--no-fund", "--no-audit"],
        ["uv", "sync", "--frozen"],
        ["npm", "run", "build"],
    ]
