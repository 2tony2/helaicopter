from __future__ import annotations

from pathlib import Path


def test_launchd_plist_template_points_at_worker_wrapper() -> None:
    template_path = Path("ops/launchd/com.helaicopter.prefect-worker.plist.template")

    assert template_path.is_file()

    template = template_path.read_text(encoding="utf-8")

    assert "ops/scripts/prefect-worker.sh" in template
    assert "{{REPO_ROOT}}" in template
    assert "<key>KeepAlive</key>" in template


def test_worker_wrapper_uses_caffeinate_and_prefect_worker_pool() -> None:
    script_path = Path("ops/scripts/prefect-worker.sh")

    assert script_path.is_file()

    script = script_path.read_text(encoding="utf-8")

    assert "caffeinate" in script
    assert "prefect worker start" in script
    assert "--pool \"${OATS_PREFECT_WORK_POOL:-local-macos}\"" in script
    assert "PREFECT_API_URL" in script
    assert "/opt/homebrew/bin" in script
    assert "/usr/local/bin" in script
    assert ".nvm/versions/node/v22.18.0/bin" in script


def test_local_ops_runbook_covers_service_lifecycle_logs_and_env() -> None:
    runbook_path = Path("docs/prefect-local-ops.md")

    assert runbook_path.is_file()

    runbook = runbook_path.read_text(encoding="utf-8")

    assert "launchctl bootstrap" in runbook
    assert "launchctl bootout" in runbook
    assert "stdout.log" in runbook
    assert "stderr.log" in runbook
    assert "PREFECT_API_URL" in runbook
    assert "OATS_PREFECT_WORK_POOL" in runbook
