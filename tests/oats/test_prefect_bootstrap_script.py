from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_prefect_bootstrap_script_exists_with_required_steps() -> None:
    script = REPO_ROOT / "bin" / "oats-prefect-up"

    assert script.exists()

    text = script.read_text(encoding="utf-8")

    assert "docker compose" in text
    assert "ops/prefect/.env" in text
    assert "curl http://127.0.0.1:4200/api/health" in text
    assert "prefect work-pool create local-macos --type process" in text
    assert "launchctl bootstrap" in text
    assert "launchctl kickstart -k" in text
    assert "uv run oats prefect deploy" not in text
    assert "uv run oats prefect run" not in text
