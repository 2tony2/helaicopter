from __future__ import annotations

from pathlib import Path

from prefect.utilities.filesystem import filter_files


def test_prefectignore_excludes_volatile_runtime_artifacts(tmp_path: Path) -> None:
    ignore_file = Path(__file__).resolve().parents[2] / ".prefectignore"
    patterns = ignore_file.read_text().splitlines()

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "python").mkdir()
    (repo / "python" / "app.py").write_text("print('ok')\n")
    (repo / ".next" / "dev" / "cache").mkdir(parents=True)
    (repo / ".next" / "dev" / "cache" / "volatile.sst").write_text("cache\n")
    (repo / ".oats" / "logs").mkdir(parents=True)
    (repo / ".oats" / "logs" / "run.log").write_text("log\n")
    (repo / ".oats-worktrees").mkdir()
    (repo / ".oats-worktrees" / "task.txt").write_text("task\n")

    included = filter_files(root=repo, ignore_patterns=patterns)

    assert "python/app.py" in included
    assert ".next/dev/cache/volatile.sst" not in included
    assert ".oats/logs/run.log" not in included
    assert ".oats-worktrees/task.txt" not in included
