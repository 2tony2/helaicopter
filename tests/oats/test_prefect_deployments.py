from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from oats.cli import app
from oats.prefect.compiler import compile_run_definition
from oats.prefect.deployments import (
    RegisteredDeployment,
    deploy_run_spec,
    read_flow_run_status,
    trigger_run_spec,
)
from oats.run_definition import (
    CanonicalExecutionHints,
    CanonicalRunDefinition,
    CanonicalTaskDefinition,
)


class StubPrefectClient:
    def __init__(self) -> None:
        self.lookup_calls: list[tuple[str, str]] = []
        self.created_payloads: list[dict[str, object]] = []
        self.updated_payloads: list[tuple[str, dict[str, object]]] = []
        self.flow_run_requests: list[tuple[str, dict[str, object]]] = []
        self.flow_run_reads: list[str] = []
        self.deployment_lookup_result: dict[str, object] | None = None

    def find_deployment_by_name(
        self,
        *,
        flow_name: str,
        deployment_name: str,
    ) -> dict[str, object] | None:
        self.lookup_calls.append((flow_name, deployment_name))
        return self.deployment_lookup_result

    def create_deployment(self, payload: dict[str, object]) -> dict[str, object]:
        self.created_payloads.append(payload)
        return {"id": "deployment-created", "name": payload["name"]}

    def update_deployment(
        self,
        deployment_id: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        self.updated_payloads.append((deployment_id, payload))
        return {"id": deployment_id, "name": payload["name"]}

    def create_flow_run_from_deployment(
        self,
        deployment_id: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        self.flow_run_requests.append((deployment_id, payload))
        return {
            "id": "flow-run-123",
            "name": "manual-run",
            "state": {"type": "SCHEDULED", "name": "Scheduled"},
        }

    def read_flow_run(self, flow_run_id: str) -> dict[str, object]:
        self.flow_run_reads.append(flow_run_id)
        return {
            "id": flow_run_id,
            "name": "manual-run",
            "state": {"type": "RUNNING", "name": "Running"},
        }


def test_deploy_run_spec_creates_a_prefect_deployment_when_missing() -> None:
    client = StubPrefectClient()

    result = deploy_run_spec(
        _sample_run_definition(),
        _repo_config(),
        client=client,
    )

    assert result == RegisteredDeployment(
        deployment_id="deployment-created",
        deployment_name="helaicopter-run-prefect-deploy-smoke",
        flow_name="oats-compiled-run",
        created=True,
    )
    assert client.lookup_calls == [
        ("oats-compiled-run", "helaicopter-run-prefect-deploy-smoke")
    ]
    assert len(client.created_payloads) == 1
    assert client.updated_payloads == []
    assert client.created_payloads[0]["name"] == "helaicopter-run-prefect-deploy-smoke"
    assert client.created_payloads[0]["work_pool_name"] == "local-macos"


def test_deploy_run_spec_updates_existing_deployment_in_place() -> None:
    client = StubPrefectClient()
    client.deployment_lookup_result = {
        "id": "deployment-existing",
        "name": "helaicopter-run-prefect-deploy-smoke",
    }

    result = deploy_run_spec(
        _sample_run_definition(),
        _repo_config(),
        client=client,
    )

    assert result == RegisteredDeployment(
        deployment_id="deployment-existing",
        deployment_name="helaicopter-run-prefect-deploy-smoke",
        flow_name="oats-compiled-run",
        created=False,
    )
    assert client.created_payloads == []
    assert len(client.updated_payloads) == 1
    assert client.updated_payloads[0][0] == "deployment-existing"
    assert client.updated_payloads[0][1]["parameters"] == {
        "payload": compile_run_definition(
            _sample_run_definition(),
            _repo_config(),
        ).flow_payload.model_dump(mode="json")
    }


def test_trigger_run_spec_creates_manual_flow_run_from_markdown_spec() -> None:
    client = StubPrefectClient()
    client.deployment_lookup_result = {
        "id": "deployment-existing",
        "name": "helaicopter-run-prefect-deploy-smoke",
    }

    flow_run = trigger_run_spec(
        _sample_run_definition(),
        _repo_config(),
        client=client,
    )

    assert flow_run.flow_run_id == "flow-run-123"
    assert flow_run.state_type == "SCHEDULED"
    assert client.flow_run_requests == [
        (
            "deployment-existing",
            {
                "parameters": {
                    "payload": compile_run_definition(
                        _sample_run_definition(),
                        _repo_config(),
                    ).flow_payload.model_dump(mode="json")
                },
                "tags": ["manual"],
            },
        )
    ]


def test_read_flow_run_status_returns_current_state() -> None:
    client = StubPrefectClient()

    status = read_flow_run_status("flow-run-123", client=client)

    assert status.flow_run_id == "flow-run-123"
    assert status.state_type == "RUNNING"
    assert status.state_name == "Running"
    assert client.flow_run_reads == ["flow-run-123"]


def test_prefect_cli_help_exposes_deploy_run_and_status_commands() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "prefect" in result.stdout
    assert "Primary path:" in result.stdout
    assert "deploy, run, status." in result.stdout
    assert "top-level commands available." in result.stdout


def test_prefect_cli_help_labels_legacy_runtime_commands_as_compatibility_only() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0
    assert "Legacy compatibility command." in result.stdout
    assert "Use `oats prefect run`." in result.stdout


def test_prefect_cli_deploy_rejects_non_markdown_run_specs() -> None:
    runner = CliRunner()

    with runner.isolated_filesystem():
        invalid_run_spec = Path("run.yaml")
        invalid_run_spec.write_text("title: invalid\n", encoding="utf-8")

        result = runner.invoke(app, ["prefect", "deploy", str(invalid_run_spec)])

    assert result.exit_code == 1
    assert "Markdown run specs are the only supported input" in result.stdout


def _sample_run_definition() -> CanonicalRunDefinition:
    repo_root = Path("/tmp/helaicopter")
    return CanonicalRunDefinition(
        title="Run: Prefect Deploy Smoke",
        source_path=repo_root / "examples" / "prefect_deploy_smoke.md",
        repo_root=repo_root,
        config_path=repo_root / ".oats" / "config.toml",
        default_validation_commands=["uv run --group dev pytest -q"],
        execution=CanonicalExecutionHints(
            repo_base_branch="main",
            worktree_dir=".oats-worktrees",
            default_concurrency=3,
        ),
        tasks=[
            CanonicalTaskDefinition(
                task_id="deploy",
                title="Deploy",
                prompt="Register the deployment.",
                validation_commands=["uv run --group dev pytest -q tests/oats/test_prefect_deployments.py"],
            )
        ],
    )


def _repo_config():
    from oats.models import RepoConfig

    return RepoConfig.model_validate(
        {
            "agent": {
                "codex": {"command": "codex", "args": ["exec"]},
                "claude": {"command": "claude", "args": []},
            }
        }
    )
