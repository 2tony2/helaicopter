from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_launchd_worker_assets_exist_and_reference_worker_wrapper() -> None:
    plist_template = REPO_ROOT / "ops" / "launchd" / "com.helaicopter.prefect-worker.plist.template"
    worker_wrapper = REPO_ROOT / "ops" / "scripts" / "prefect-worker.sh"
    runbook = REPO_ROOT / "docs" / "prefect-local-ops.md"

    assert plist_template.exists()
    assert worker_wrapper.exists()
    assert runbook.exists()

    plist_text = plist_template.read_text()
    wrapper_text = worker_wrapper.read_text()

    assert "ops/scripts/prefect-worker.sh" in plist_text
    assert "caffeinate" in wrapper_text
    assert "prefect worker start --pool local-macos" in wrapper_text
