from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_prefect_bootstrap_script_exists_with_required_steps() -> None:
    script = REPO_ROOT / "bin" / "oats-prefect-up"

    assert script.exists()

    text = script.read_text(encoding="utf-8")

    assert "docker compose" in text
    assert "ops/prefect/.env" in text
    assert "curl http://127.0.0.1:4200/api/health" in text
    assert 'export PREFECT_API_URL="${PREFECT_API_URL:-http://127.0.0.1:4200/api}"' in text
    assert "uv run prefect work-pool create local-macos --type process" in text
    assert "uv run prefect work-pool inspect local-macos" in text
    assert "launchctl print" in text
    assert "launchctl bootstrap" in text
    assert "launchctl kickstart -k" in text
    assert "uv run oats prefect deploy" not in text
    assert "uv run oats prefect run" not in text


def test_dev_script_bootstraps_prefect_before_api_and_web() -> None:
    dev_script = (REPO_ROOT / "scripts" / "dev.mjs").read_text(encoding="utf-8")

    assert "bin/oats-prefect-up" in dev_script
