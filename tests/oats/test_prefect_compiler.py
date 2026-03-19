from __future__ import annotations

from pathlib import Path

import pytest

from oats.models import RepoConfig
from oats.prefect.compiler import (
    SHARED_FLOW_ENTRYPOINT,
    SHARED_FLOW_NAME,
    compile_run_definition,
)
from oats.run_definition import (
    CanonicalExecutionHints,
    CanonicalRunDefinition,
    CanonicalTaskDefinition,
)


def test_compile_run_definition_preserves_dependency_edges() -> None:
    deployment = compile_run_definition(_sample_run_definition(), _repo_config())

    assert [(edge.upstream_task_id, edge.downstream_task_id) for edge in deployment.task_graph.edges] == [
        ("plan", "build"),
        ("plan", "verify"),
        ("build", "verify"),
    ]
    assert [node.task_id for node in deployment.task_graph.nodes] == ["plan", "build", "verify"]
    assert deployment.flow_payload.tasks[2].depends_on == ["plan", "build"]


def test_compile_run_definition_uses_deterministic_routing_and_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OATS_PREFECT_WORK_POOL", "review-pool")
    monkeypatch.setenv("OATS_PREFECT_DEFAULT_QUEUE", "overnight")

    first = compile_run_definition(_sample_run_definition(), _repo_config())
    second = compile_run_definition(_sample_run_definition(), _repo_config())

    assert first == second
    assert first.flow_name == SHARED_FLOW_NAME
    assert first.entrypoint == SHARED_FLOW_ENTRYPOINT
    assert first.deployment_name == "helaicopter-run-prefect-compiler-smoke"
    assert first.work_pool_name == "review-pool"
    assert first.work_queue_name == "overnight"
    assert first.tags == [
        "base-branch:main",
        "oats",
        "repo:helaicopter",
        "run:run-prefect-compiler-smoke",
    ]


def test_compile_run_definition_embeds_reusable_shared_flow_payload() -> None:
    deployment = compile_run_definition(_sample_run_definition(), _repo_config())

    assert deployment.parameters == {
        "payload": deployment.flow_payload.model_dump(mode="json")
    }
    assert deployment.flow_payload.repo_root == Path("/tmp/helaicopter")
    assert deployment.flow_payload.config_path == Path("/tmp/helaicopter/.oats/config.toml")
    assert deployment.flow_payload.task_graph.edges[0].upstream_task_id == "plan"


def _sample_run_definition() -> CanonicalRunDefinition:
    repo_root = Path("/tmp/helaicopter")
    return CanonicalRunDefinition(
        title="Run: Prefect Compiler Smoke",
        source_path=repo_root / "examples" / "prefect_compiler_smoke.md",
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
                task_id="plan",
                title="Plan",
                prompt="Write the plan.",
                validation_commands=["uv run --group dev pytest -q tests/test_plan.py"],
            ),
            CanonicalTaskDefinition(
                task_id="build",
                title="Build",
                prompt="Implement the compiler.",
                depends_on=["plan"],
                acceptance_criteria=["compiler exists"],
            ),
            CanonicalTaskDefinition(
                task_id="verify",
                title="Verify",
                prompt="Run validation.",
                depends_on=["plan", "build"],
                notes=["keep payload reusable"],
            ),
        ],
    )


def _repo_config() -> RepoConfig:
    return RepoConfig.model_validate(
        {
            "agent": {
                "codex": {"command": "codex", "args": ["exec"]},
                "claude": {"command": "claude", "args": []},
            }
        }
    )
